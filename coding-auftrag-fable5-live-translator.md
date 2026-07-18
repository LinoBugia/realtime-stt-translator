# Coding-Auftrag: Live Speech Translator (fuer Claude Fable 5)

> Zum Einfuegen als Prompt in Claude Fable 5. Klar und intent-fokussiert gehalten
> (Fable 5 arbeitet besser mit klarer Absicht als mit ueberladenen Mega-Prompts).

---

## Ziel

Baue eine **browserbasierte Web-App** zum Sprachenueben. Ich spreche (oder spiele Audio ab),
die App transkribiert live via ElevenLabs Scribe v2 Realtime und zeigt **sofort** die
Uebersetzung via DeepL. Zweck: ich sehe in Echtzeit, was ich gerade auf Spanisch/Deutsch/
Englisch sage, um meine Sprachkenntnisse zu verbessern.

Sprachen v1: **Englisch, Spanisch, Deutsch, Polnisch, Italienisch, Portugiesisch,Franzoesisch** — jede als 
Quelle UND Ziel frei kombinierbar (alle Richtungen). 

## Kern-User-Flow

1. Ich waehle Quellsprache und eine oder zwei Zielsprachen.
2. Ich klicke "Start" -> Mikrofon-Aufnahme beginnt.
3. Audio streamt live an ElevenLabs Scribe v2 Realtime (WebSocket).
4. Partielle Transkripte erscheinen sofort live (grau/kursiv), finalisierte
   (committed) Transkripte werden fixiert (schwarz).
5. Jedes committed Segment wird an DeepL geschickt und die Uebersetzung
   erscheint direkt daneben.
6. Verlauf der Saetze bleibt sichtbar (scrollbare Liste: Original | Uebersetzung).

## Architektur (wichtig: API-Keys NIE im Frontend)

Zwei Teile:

### Frontend (Browser)
- Mikrofon-Capture (Web Audio API), PCM 16-bit / 16 kHz / mono.
- Direkte WebSocket-Verbindung zu ElevenLabs Scribe v2 Realtime — authentifiziert
  ueber einen **Single-Use-Token**, den das Backend ausstellt (Key bleibt geheim).
- Unterscheide **partial** (live, ungesichert) vs **committed** (finalisiert) Transkripte.
- Commit-Strategie: **VAD** (automatisch bei Sprechpause committen).
- UI (siehe unten).

### Backend (minimal, z.B. Node/Express oder Python/FastAPI — Fable waehlt)
- `POST /api/elevenlabs/token` -> erzeugt serverseitig einen Single-Use-Token
  fuer Scribe Realtime (nutzt `ELEVENLABS_API_KEY` aus .env).
- `POST /api/translate` -> Proxy zu DeepL (`{ text, source_lang, target_lang }`).
  Nutzt `DEEPL_API_KEY` aus .env, Endpoint `https://api-free.deepl.com/v2/translate`.
  Reiche `formality` und optional `context` (vorheriger Satz) durch.
- Beide Keys ausschliesslich serverseitig, via `.env`. `.env.example` mitliefern.

## STT-Details (ElevenLabs)
- Modell: **`scribe_v2_realtime`** (NICHT der Batch-Modus `scribe_v2`).
- Verbindung per WebSocket, ~150 ms Latenz.
- Mikrofon-Flags: `echoCancellation: true`, `noiseSuppression: true`.
- Zeige partial live, ersetze durch committed sobald finalisiert.

## Translate-Details (DeepL)
- DeepL API Free (`api-free.deepl.com`).
- Pro committed Segment ein Translate-Call.
- **`formality`** je Zielsprache waehlbar (formell/informell) — als UI-Toggle,
  relevant fuer DE und ES.
- **`context`**: den vorherigen Satz als Kontext mitschicken (verbessert Qualitaet,
  wird nicht mituebersetzt).
- Optional: Glossar-Hook vorsehen (fuer eigene Fachbegriffe), auch wenn v1 leer.
- Throttling: veraltete Interim-Uebersetzungen verwerfen (Message-Versioning),
  damit bei schnellem Sprechen keine Uebersetzungs-Queue auflaeuft.

## UI-Anforderungen
- Klares, ruhiges Layout: zweispaltig **Original | Uebersetzung**, chronologisch,
  neuestes unten, auto-scroll.
- Oben: Quellsprache-Dropdown, Zielsprache(n)-Dropdown(s), Formality-Toggle,
  grosser Start/Stop-Mikrofon-Button.
- Live-Zeile fuer partielles Transkript optisch abgesetzt (grau/kursiv).
- Kleiner Latenz-/Status-Indikator (verbunden / hoert zu / Fehler).
- Dark-Mode.
- Responsive, funktioniert auf Desktop-Chrome.

## Nicht-Ziele (v1 bewusst weglassen)
- Kein LLM-Grammatik-Analyse-Layer (kommt in v2).
- Kein Multi-User / Broadcast / Login / Datenbank.
- Kein Text-to-Speech.

## Tech-Stack (Vorschlag, Fable darf abweichen)
- Frontend: Vite + TypeScript (React optional, kann auch vanilla sein).
- Backend: schlanker Node/Express **oder** Python/FastAPI Server.
- Ein `npm run dev` / ein Kommando startet Frontend + Backend lokal.
- Keine schwergewichtigen Abhaengigkeiten wenn vermeidbar.

## Sicherheit & Config
- `ELEVENLABS_API_KEY` und `DEEPL_API_KEY` nur im Backend, via `.env`.
- `.env.example` mit Platzhaltern und Kommentaren.
- Keys niemals ins Frontend-Bundle oder in Git.

## Akzeptanzkriterien
1. Ich spreche Spanisch -> sehe live spanisches Transkript und sofort die
   deutsche (und/oder englische) Uebersetzung daneben.
2. Sprachrichtungen EN/ES/DE/PL/FR/... in alle Richtungen frei kombinierbar.
3. Keys bleiben serverseitig; im Browser-Netzwerk-Tab ist kein API-Key sichtbar.
4. Kurze Saetze erscheinen uebersetzt in ~unter 1 s nach Sprechpause.
5. README mit Setup-Schritten (Keys eintragen, starten).

## Roadmap-Notiz fuer spaeter (nicht v1 bauen)
- v2: committed Transkript + Uebersetzung an ein LLM (lokal via Ollama oder API)
  schicken -> Grammatik-/Wortwahl-Feedback ("was war falsch, bessere Formulierung").
- Modularer Translate-Layer, damit DeepL spaeter gegen Alternativen tauschbar bleibt.
