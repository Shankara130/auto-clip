# auto-clip — Design Document

> Status: Design (living document). This is the canonical reference for the system.
> Catatan belajar: dokumen ini adalah **spesifikasi desain**, bukan kode siap-jalan. Implementasi Python ditulis sendiri oleh developer sebagai bagian dari proses belajar. Query Cypher di bawah adalah *ilustrasi desain*.

---

## 1. Konteks & Tujuan

**auto-clip** mengubah video panjang (podcast / stream / talk, 30–180 menit) menjadi beberapa klip pendek (~15–90 detik, untuk YouTube Shorts / Reels / TikTok).

**Pembeda utama:** graph database **Neo4j** merekomendasikan momen mana yang "terbaik" untuk dipotong — bukan sekadar skor per segmen, melainkan dengan memanfaatkan **hubungan** antar segmen, topik, entitas, pembicara, dan performa historis klip masa lalu. Untuk konten *live*, ditambah sinyal **reaksi live chat** sebagai *ground truth* kerumunan.

### Keputusan yang sudah dikunci
- **Bahasa:** Python (FastAPI). (Go pernah dipertimbangkan, ditolak.)
- **Database:** Neo4j adalah *pusat* ("otak"), bukan sekadar penyimpanan. Plugin APOC + GDS.
- **Deployment:** Docker Compose lokal.
- **Transkripsi:** faster-whisper (lokal, timestamp per kata) dengan fallback API OpenAI.
- **Clipping & subtitle:** ffmpeg (libass untuk caption animasi).
- **Prinsip:** harus bisa jalan end-to-end di CPU tanpa API key — semua dependensi eksternal punya fallback.

### Prinsip pemandu
1. **Graph = otak.** Nilai sebuah momen adalah fungsi dari *tetangganya* (traversal), bukan `SELECT … ORDER BY score`.
2. **Pipeline idempoten.** Kunci identitas stabil + `MERGE … ON CREATE/ON MATCH`. Mengulang video tidak pernah menduplikasi node.
3. **Degrade, bukan gagal.** Setiap dependensi (GPU/Whisper, key OpenAI, GDS) diperiksa saat startup dan dialihkan ke fallback bila absen.
4. **Pipeline asinkron + API sinkron.** Ingest = pekerjaan latar yang panjang; HTTP tetap responsif (BackgroundTasks untuk MVP, Celery nanti, di balik abstraksi job).
5. **Semua Cypher ada di repository**, tidak pernah di route.

---

## 2. Glosarium (istilah penting)

| Istilah | Arti |
|---|---|
| **Segment (momen)** | Satu potongan kandidat dari video (rentang waktu + transkrip). |
| **Clip** | Hasil akhir yang dirender dari satu/lebih segment. |
| **Node** | Titik dalam graph (Video, Segment, Topic, Entity, …). |
| **Relationship** | Garis penghubung antar node, punya arah & bisa punya properti. |
| **Graph traversal** | Menelusuri node lewat relationship (inti kekuatan Neo4j). |
| **Centrality / PageRank** | Ukur "kepentingan" sebuah node berdasarkan posisinya di graph. |
| **Peak detection** | Mencari puncak (lonjakan) dalam deret data waktu. |

---

## 3. Arsitektur Tingkat Tinggi

```
   client ──REST──▶ FastAPI app ──Cypher──▶ Neo4j 5.x (+APOC +GDS)
                       │ async
                  Job runner ──ffmpeg──▶ clips/ (caption dibakar)
                       │      ──whisper──▶ transcript ──LLM──▶ analysis ──▶ graph
                       │      ──[chat]──▶ hype signal ──▶ graph (opsional, untuk live)
```

**Alur data utama:**
Ingest → Transcribe → (Diarize, opsional) → Segment → Analyze → Graph-build → Recommend → Render (+captions).

---

## 4. Skema Graph Neo4j (inti)

### 4.1 Node
| Label | Mengapa graph (bukan SQL) | Properti kunci |
|---|---|---|
| `Video` | Jangkar sub-graph; satu traversal menyebar ke seluruh segmen/klip. | `id`(PK), `source_uri`, `title`, `duration_s`, `language`, `status`, `audio_path` |
| `Segment` (momen kandidat) | Mewarisi kepentingan dari topik/entitas + klip masa lalu yang mirip. Membawa **fitur lokal**. | `id`(PK=`{video}:{ordinal}`), `ordinal`, `start_s`, `end_s`, `text`, `duration_s`, `hook_score`, `sentiment_score`, `energy_score`, `information_density`, `chat_hype`(opsional), `local_score`, `graph_score`, `final_score`, `recommended` |
| `Speaker` | "Kalimat terbaik host", keseimbangan klip, dinamika co-host. | `id`, `name`, `total_speech_s` |
| `Topic` | **Trend boost**, **diversitas**, akumulasi performa per topik. Sedikit & dikurasi LLM. | `id`(slug), `name`, `perf_views_avg`, `perf_retention_p70` |
| `Entity` (NER) | **Centrality (PageRank)**, co-occurrence, riwayat entitas. | `id`, `name`, `kind`, `pagerank`, `_mention_degree` |
| `Keyword` | Frasa kunci padat & murah untuk edge similarity. Banyak. | `id`, `text`, `df` |
| `Clip` | Output. Terhubung balik ke Segment agar performa mengalir balik. | `id`, `video_id`, `start_s`, `end_s`, `title`, `platform`, `aspect`, `status`, `render_path` |
| `Performance` | Engagement time-series (node terpisah → hitung *velocity*, sinyal asli). | `id`, `views`, `likes`, `shares`, `retention_pct`, `captured_at` |
| `TrendingTerm` | Sinyal tren eksternal; boost segmen lewat fan topik. | `id`, `term`, `platform`, `volume`, `as_of` |
| `ChatReaction` (opsional, untuk live) | Sinyal reaksi kerumunan per segmen. | `id`, `msg_rate`, `hype_score`, `top_emotes`, `clip_mentions`, `captured_at` |
| `Audience` | Ranking per-audiens (masa depan). | `id`, `name`, `platform` |

### 4.2 Relationship (berarah)
| Relationship | Mengapa jadi edge |
|---|---|
| `(Video)-[:HAS_SEGMENT]->(Segment)` | Fan lokal. |
| `(Segment)-[:DISCUSSES {weight,salience}]->(Topic)` | Propagasi topik — segmen memperoleh boost/tren topik di sini. |
| `(Segment)-[:MENTIONS {count}]->(Entity)` | Propagasi centrality + co-occurrence. |
| `(Segment)-[:HAS_KEYWORD {tf}]->(Keyword)` | Similaritas padat. |
| `(Segment)-[:SPOKEN_BY]->(Speaker)` | Keseimbangan pembicara. |
| `(Segment)-[:SIMILAR_TO {score}]->(Segment)` | Cosine terhitung — **edge yang membuat redundansi jadi masalah graph.** |
| `(Segment)-[:ADJACENT_TO]->(Segment)` | Memperluas/menggabung kandidat lemah yang berdekatan. |
| `(Clip)-[:DERIVED_FROM]->(Segment)` | **Jembatan feedback**: performa mengalir balik ke Topic/Entity. |
| `(Clip)-[:HAS_PERFORMANCE]->(Performance)` | Engagement time-series. |
| `(Segment)-[:HAD_REACTION]->(ChatReaction)` | Sinyal chat (live). |
| `(Topic)-[:TRENDING_ON {boost,as_of}]->(TrendingTerm)` | Propagasi tren. |

### 4.3 Bootstrap skema (idempoten) — `db/constraints.py`
Constraint keunikan pada semua PK; lookup index pada `Segment.local_score/graph_score/final_score/video_id`, `Entity.(name,kind)`, `Video.status`; full-text index pada `Topic.name`, `Entity.name`, `Segment.text`. Semua `IF NOT EXISTS`. Dijalankan saat startup app.

Contoh (ilustrasi DDL — bagian dari spesifikasi, bukan implementasi app):
```cypher
CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE;
CREATE INDEX segment_final  IF NOT EXISTS FOR (s:Segment) ON (s.final_score);
CREATE FULLTEXT INDEX segment_fulltext IF NOT EXISTS FOR (s:Segment) ON EACH [s.text];
```

---

## 5. Mesin Rekomendasi (pembeda)

**Dua tahap: skor → diversifikasi.** Skor per-segmen saja menghasilkan 5 klip redundant tentang satu topik.

```
final_score(s) = w_local·norm(local_score) + w_graph·norm(graph_score)
                 (dinormalisasi per-video; default 0.5 / 0.5)
```

### 5.1 Fitur LOKAL (dihitung di Python, ditulis ke properti node — bukan Cypher)
`hook_score` (LLM + fallback regex), `sentiment_score` (LLM/VADER), `energy_score` (LUFS ffmpeg + kata/menit), `duration_fit` (jendela 15–90s), `information_density` (jumlah entitas+keyword/menit), `chat_hype` (opsional, lihat §6).

### 5.2 Fitur GRAPH (traversal Cypher — *ini alasan Neo4j*)
- `topic_trend_boost`: `(s)-[:DISCUSSES]->(t)-[:TRENDING_ON]->(tr)`
- `topic_perf_lift`: performa klip masa lalu dari segmen di bawah topik yang sama.
- `entity_centrality`: PageRank/articleRank via **GDS** (fallback: degree).
- `similarity_to_winners`: `(s)-[:SIMILAR_TO]->(s2)<-[:DERIVED_FROM]-(c)-[:HAS_PERFORMANCE]->(p)`

### 5.3 Contoh query graph-feature (ilustrasi desain)
```cypher
MATCH (v:Video {id:$video_id})-[:HAS_SEGMENT]->(s:Segment)
OPTIONAL MATCH (s)-[:SIMILAR_TO]->(peer:Segment)<-[:DERIVED_FROM]-(c:Clip)-[:HAS_PERFORMANCE]->(p:Performance)
WITH s, avg(p.views) AS simLift
OPTIONAL MATCH (s)-[:DISCUSSES]->(t:Topic)<-[:DISCUSSES]-(other)<-[:DERIVED_FROM]-(c2:Clip)-[:HAS_PERFORMANCE]->(p2)
WITH s, simLift, percentileCont(p2.views,0.8) AS topicLift
OPTIONAL MATCH (s)-[:DISCUSSES]->(tT:Topic)-[tr:TRENDING_ON]->(tt:TrendingTerm)
WITH s, simLift, topicLift, coalesce(sum(tr.boost),0) AS trendBoost
OPTIONAL MATCH (s)-[:MENTIONS]->(e:Entity)
WITH s, simLift*$sim_w + topicLift*$tp_w + trendBoost*$tr_w + sum(e._mention_degree)*$en_w AS graphRaw
SET s.graph_score = graphRaw
RETURN s.id, s.graph_score ORDER BY graph_score DESC;
```

### 5.4 Seleksi top-K non-redundan
Cypher memberi *predikat per ronde*, Python melakukan loop (lebih mudah diuji):
```cypher
-- tolak kandidat jika berdekatan waktu ATAU mirip dengan yang sudah dipilih
WHERE NOT ANY(ch IN $chosen WHERE
   abs(c.start_s - ch.start_s) < $min_gap_s
   OR EXISTS { (c)-[sim:SIMILAR_TO]-(ch) WHERE sim.score >= $sim_threshold })
```

### 5.5 Feedback loop & cold-start
- **Feedback:** saat `Performance` masuk, dorong sinyal balik ke Topic/Entity agar segmen masa depan langsung mewarisinya; lacak fitur mana yang berkorelasi dengan performa nyata → sesuaikan bobot.
- **Cold-start:** fitur perf/similarity/speaker → 0 (auto-renormalisasi memihak fitur lokal + struktural); isi awal dengan prior global dari seed + daftar "topik dikenal-baik"; `entity_centrality`/`trend_boost` aktif sejak hari-1; API mengembalikan `cold_start=true`.

---

## 6. Sinyal Live Chat (opsional, untuk konten live) — *fitur tambahan*

> Diusulkan pengguna: deteksi momen via analisis live chat. Sangat kuat untuk *live stream*, lemah/tidak tersedia untuk rekaman.

### 6.1 Konsep
Live chat = **sensor kerumunan real-time**. Saat momen menarik terjadi, chat "meledak". Daripada menebak dari transkrip, kita baca reaksi penonton langsung.

### 6.2 Sinyal yang diambil
- Volume pesan / detik → spike.
- **Emote** (POGGERS, KEKW) → emosi spesifik (sangat ekspresif).
- CAPS & tanda seru → hype.
- Spam kata/frasa yang sama ("CLIP IT!", nama) → sinyal langsung.
- **Awas "sentiment":** valensi (senang/tidak) kurang berguna — drama itu "negatif" tapi bagus untuk klip. Yang dipakai adalah **arousal/intensitas** + analisis emote.

### 6.3 Algoritma deteksi momen dari chat (pseudocode, konsep)
```
# 1. Bucket: kelompokkan pesan per jendela waktu (mis. 5 detik)
for each time_bucket B:
    B.score = w1*msg_count + w2*emote_count + w3*caps_count + w4*exclam + w5*repeat_tokens

# 2. Smoothing: rata-rata bergerak (window W)
smoothed = moving_average(scores, W)

# 3. Baseline: normalisasi thd rata-rata stream (penting bagi streamer besar)
normalized = smoothed / global_mean

# 4. Peak detection: cari maksimum lokal di atas ambang, prominence cukup, jarak minim
peaks = find_peaks(normalized, threshold=T, prominence=P, distance=D)

# 5. Koreksi offset (chat telat 10–30 detik)
for each peak: peak.video_time = peak.chat_time - OFFSET

# 6. Petakan ke segment video → jadi kandidat + fitur chat_hype
```

### 6.4 Integrasi ke graph
- `ChatReaction` node / properti `chat_hype` pada Segment → menjadi **fitur lokal kuat** + **ground-truth**.
- Menjadi **data berlabel** untuk feedback loop (hype chat berkorelasi performa klip).
- Emote/frasa naik daun → `Entity`/`TrendingTerm` → boost segmen.
- **Pluggable & graceful:** ada chat → pakai sinyal ini; tidak ada → fallback ke sinyal transkrip.

### 6.5 Trade-off jujur
- Hanya untuk konten live (Twitch/YouTube Live). Podcast/rekaman tidak punya chat.
- Offset waktu ~10–30 detik wajib dikoreksi.
- Noise/bot → butuh smoothing + peak detection yang baik.
- Chat sepi (stream kecil) → sinyal lemah (cold start).

---

## 7. Pipeline Pemrosesan (tahapan)

| # | Tahap | In→Out | Pendekatan | Catatan |
|---|---|---|---|---|
| 1 | Ingest | uri → `Video` + wav 16k mono | `ffmpeg-python` | id=hash(uri+size); MERGE |
| 2 | Transcribe | audio → `Segment` + timestamp per kata | faster-whisper (`word_timestamps=True`); fallback API OpenAI | timing kata → caption |
| 3 | Diarize (opsional) | audio+transkrip → `Speaker` | pyannote.audio (HF_TOKEN) else stub | gated env |
| 4 | Segment | segmen whisper → momen kandidat | potong alami: batas whisper + silence + topic-shift + >90s split + snap ke silence | deterministik |
| 5 | Analyze | tiap Segment → fitur lokal + edge DISCUSSES/MENTIONS/HAS_KEYWORD | LLM (OpenAI); **stub** = regex NER + VADER + hook naif bila tanpa key | MERGE by normalized id |
| 6 | (Live) Chat-signal | chat → hype → puncak → `ChatReaction`/`chat_hype` | §6 algoritma | opsional, perlu sumber chat |
| 7 | Graph-build | analysis → `SIMILAR_TO`, `ADJACENT_TO`, centrality | Cypher MERGE batch; SIMILAR_TO = cosine ≥ threshold (fallback keyword-TF) | semua MERGE |
| 8 | Recommend | graph → `final_score`, top-K, `Clip`(planned) | §5 | recompute menggantikan flag |
| 9 | Render | rentang Clip → mp4 9:16 + caption dibakar | ffmpeg libx264 + libass | error per-klip terisolasi |

`pipeline/runner.py` berjalan menembus tahap, memperbarui `Video.status`; error → `failed`+`error_msg`; re-POST melanjutkan dari tahap terakhir yang belum selesai.

---

## 8. Subsistem Auto Subtitle/Caption

Tujuan: menghasilkan **caption yang dibakar ke video (burned-in), bergaya, dan animasi** otomatis, plus **auto-edit** transkrip agar enak dibaca. Berada di `src/auto_clip/captions/`.

| Modul | Tanggung jawab |
|---|---|
| `transcript_to_subtitles.py` | Ubah timestamp per-kata whisper → cue terbaca (~3–7 kata/baris, 2 baris max, hormati kecepatan baca). |
| `caption_editor.py` (auto-edit) | Buang filler word (um, uh), perbaiki tanda baca/kapital, gabung fragmen, rapikan overlap. LLM bila ada key, **fallback aturan** bila tidak. |
| `ass_writer.py` | Hasilkan **.ass** untuk kontrol halus: timing karaoke per kata, stroke, shadow, posisi, font. |
| `styles.py` | **Preset** caption: `karaoke_pop` (default — kata aktif terhighlight+zoom, gaya Opus Clip), `clean_bold`, `minimal`. |
| `emphasis.py` | **Penekanan sadar-graph:** `Entity` bercentrality tinggi & `Topic` tren disorot (warna/skala) di caption — menghubungkan subtitle ke "otak" graph. |

**Burn-in:** ffmpeg `subtitles=clip.ass` (libass) di tahap Render → mp4 9:16 final dengan caption.

---

## 9. Struktur Proyek

```
auto-clip/
├── docker-compose.yml  Dockerfile  requirements.txt  requirements-dev.txt
├── .env.example  README.md  Makefile
├── docs/DESIGN.md                   # dokumen ini
├── data/{audio,segments,clips,uploads,seeds/seed.cypher}
└── src/auto_clip/
    ├── main.py                      # app factory + lifespan (probe deps, bootstrap skema)
    ├── core/{config,logging,exceptions}.py
    ├── api/{deps.py, routes/{videos,clips,recommend,trends,health}.py}
    ├── db/
    │   ├── neo4j_driver.py          # singleton, health, deteksi GDS
    │   ├── constraints.py           # bootstrap skema idempoten
    │   └── repositories/{video,segment,clip,graph}_repo.py   # SEMUA Cypher di sini
    ├── transcription/{base.py(Protocol),faster_whisper.py,openai_whisper.py,diarization.py}
    ├── analysis/{base.py(Protocol),llm_analyser.py,stub_analyser.py,features.py}
    ├── chat/{collector,scorer,peak_detect}.py              # sinyal live chat (opsional)
    ├── segmentation/cutter.py
    ├── captions/{transcript_to_subtitles,caption_editor,ass_writer,styles,emphasis}.py
    ├── rendering/ffmpeg_clipper.py  # membakar .ass caption
    ├── recommend/{scoring,graph_features,diversify,feedback}.py
    ├── pipeline/{stages,runner,jobs}.py
    ├── models/                      # pydantic DTO
    └── seeds/load_seed.py
└── tests/{conftest,fixtures/sample.mp4,...}
```

---

## 10. Tech Stack & Dependensi (`requirements.txt`)

```
fastapi==0.115.*            uvicorn[standard]==0.32.*
pydantic==2.9.*             pydantic-settings==2.6.*
neo4j==5.27.*               # driver 5.x cocok image Neo4j-5
faster-whisper==1.2.1       # BERAT (~150MB, TANPA torch) — default CPU
openai==1.54.*              # fallback Whisper API + analisis LLM
ffmpeg-python==0.2.*
python-multipart==0.0.12  httpx==0.27.*  tenacity==9.0.*  orjson==3.10.*  pyyaml==6.0.*
# OPSIONAL (menarik torch ~2GB) — sistem jalan TANPA-nya; gated env:
# pyannote.audio==3.3.*            (diarization; butuh HF_TOKEN)
# sentence-transformers==3.3.*     (embedding SIMILAR_TO; else keyword-TF)
# chat: chatdownloader / twitch-irc  (sumber live chat, opsional)
# dev: pytest==8.3.*  pytest-asyncio==0.24.*  testcontainers[neo4j]==4.8.*  ruff==0.7.*  mypy==1.13.*
```
**ffmpeg** adalah binary sistem di image Docker (`apt-get install ffmpeg`), bukan pip.

---

## 11. Config & Env (`.env.example`) — semua punya default CPU/tanpa-key
```
APP_HOST=0.0.0.0  APP_PORT=8000  LOG_LEVEL=INFO  DATA_DIR=./data
NEO4J_URI=bolt://neo4j:7687  NEO4J_USER=neo4j  NEO4J_PASSWORD=autoclipdev  NEO4J_DATABASE=neo4j
WHISPER_PROVIDER=faster_whisper  WHISPER_MODEL=base  WHISPER_DEVICE=cpu  WHISPER_COMPUTE_TYPE=int8
DIARIZATION_ENABLED=false  HF_TOKEN=
LLM_PROVIDER=openai  OPENAI_API_KEY=         # KOSONG → auto-stub analyser
OPENAI_MODEL=gpt-4o-mini  EMBEDDINGS_PROVIDER=none
CHAT_ENABLED=false  CHAT_SOURCE=none  CHAT_OFFSET_S=15  CHAT_BUCKET_S=5
REC_K=5  REC_MIN_DURATION_S=15  REC_MAX_DURATION_S=90  REC_FINAL_MIN=0.35
REC_SIM_THRESHOLD=0.75  REC_MIN_GAP_S=30  REC_W_LOCAL=0.5  REC_W_GRAPH=0.5
CAPTIONS_ENABLED=true  CAPTIONS_STYLE=karaoke_pop  CAPTIONS_MAX_WORDS_PER_LINE=5
CAPTIONS_FILLER_WORDS=true  CAPTIONS_HIGHLIGHT_ENTITIES=true
RENDER_PRESET=veryfast
```

---

## 12. Build Bertahap / Modul Belajar

| Fase/Modul | Hasil belajar | Output |
|---|---|---|
| **0 — Fondasi Python & infra** | Dasar Python, Docker Compose, Cypher dasar, Python↔Neo4j, FastAPI + config | App jalan & sehat |
| **1 — Vertical slice** | ffmpeg, faster-whisper, segmentasi, struktur proyek | Klip pertama keluar |
| **2 — Graph modeling** | Desain skema, MERGE idempoten, constraints/indexes | Graph terisi |
| **3 — Mesin rekomendasi** | Traversal Cypher, GDS/PageRank, scoring, diversifikasi | Rekomendasi momen terbaik |
| **3b — Live chat signal** | Peak detection, smoothing, offset alignment (§6) | Sinyal kerumunan |
| **4 — Subtitle + feedback** | Caption ASS animasi, ffmpeg libass, feedback loop | Klip dengan caption |

**Slice pertama yang direkomendasikan = Fase 0 + 1** — menghasilkan klip yang terlihat dan men-de-risk dua integrasi terberat (whisper di CPU, ffmpeg caption) sebelum logika graph apa pun.

---

## 13. Verifikasi (end-to-end lokal)

**Video nyata:** salin `sample.mp4` ke `data/uploads/` → `make up` → `POST /videos` → poll `GET /videos/{id}` → `GET /recommend` → `GET /clips/{id}/download`. Konfirmasi mp4 9:16 dengan caption animasi terbakar.

**Demo seeded tanpa video nyata** (membuktikan pembeda): `make seed` memuat `data/seeds/seed.cypher` (1 Video, ~25 Segment, 4 Topic dgn 2 trending, 12 Entity, 3 Speaker, beberapa Clip+Performance, edge SIMILAR_TO). `POST /recommend?k=4` → 4 segment mencakup ≥2 topik, topik trending terlihat di-boost, tak ada pasangan terpilih SIMILAR_TO≥threshold. **Kontrak uji:** `len(set(chosen_topics)) >= 2` dan tak ada pasangan melebihi ambang similarity — bukti graph layak dipakai.

**Matriks kapabilitas** di `GET /health`:
```json
{"neo4j":"ok","gds":"absent","whisper":"faster_whisper/cpu","diarization":"stub","llm":"stub","embeddings":"keyword_tf","chat":"disabled","captions":"karaoke_pop"}
```

---

## 14. File Kritis (urutan implementasi)
- `src/auto_clip/db/constraints.py` — bootstrap skema idempoten; menopang semua MERGE.
- `src/auto_clip/db/repositories/graph_repo.py` — semua Cypher graph (build + fitur).
- `src/auto_clip/recommend/graph_features.py` — Cypher yang membuat graph layak.
- `src/auto_clip/recommend/diversify.py` — top-K non-redundan via SIMILAR_TO.
- `src/auto_clip/chat/peak_detect.py` — deteksi puncak chat (§6).
- `src/auto_clip/captions/{ass_writer,caption_editor}.py` — subtitle auto-edit animasi.
- `src/auto_clip/rendering/ffmpeg_clipper.py` — burn-in caption.
- `src/auto_clip/pipeline/runner.py` — orkestrasi tahap + resume berbasis status.
- `data/seeds/seed.cypher` — graph demo yang membuktikan pembeda rekomendasi.

---

## 15. Pertanyaan Terbuka / Masa Depan
- Sumber chat mana yang didukung duluan (Twitch IRC vs YouTube live_chat vs VOD)?
- Model embed untuk SIMILAR_TO: lokal (sentence-transformers) vs API?
- Apakah caption karaoke dibakar (lebih cepat, tak bisa diubah) atau soft-sub (fleksibel)?
- Skala: kapan pindah dari BackgroundTasks ke Celery? Kapan `SIMILAR_TO` pindah ke GDS `nodeSimilarity`?
