# GitHub PR Review Debt Tracker - Supabase verzija

Izvlači GitHub PR review komentare i sprema ih u Supabase bazu podataka. Omogućuje tracking, filtriranje i akcije na komentarima.

## Setup

### 1. Instaliraj dependencies

```bash
pip install -r requirements.txt
```

### 2. Postavi .env datoteku

Kopiraj `.env.example` u `.env` i popuni kredencijale:

```bash
cp .env.example .env
```

Otvorite `.env` i dodajte vaše Supabase kredencijale:

```
SUPABASE_URL=https://vvwbpfvclcqryoqxozmk.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 3. Kreiraj tablicu u Supabase

Pokreni SQL skriptu `create_supabase_table.sql` u Supabase SQL editoru.

## Korištenje

### Osnovni primjer - spremi samo u Supabase

```bash
# U git repositoriumu - auto-detektuje repo
python export_pr_comments.py

# Ili eksplicitno navedi repo
python export_pr_comments.py owner/repo

# Posljednjih 14 dana
python export_pr_comments.py owner/repo --days 14
```

### Sa CSV exportom

```bash
# Spremi i u Supabase i u CSV
python export_pr_comments.py --to-csv

# Custom CSV datoteka
python export_pr_comments.py --to-csv -o my_comments.csv
```

## Kako radi

1. **Preuzimanje PR-ova** — `gh pr list` nalazi sve PR-ove koji su se mijenjali u zadnjih N dana
2. **Preuzimanje komentara** — Za svaki PR, uzima review komentare s GitHub API-ja
3. **Upsert u Supabase** — Sprema komentare u `pr_comments` tablicu
   - Nove komentare dodaje
   - Duplikate ignorira (po `comment_url`)
4. **CSV opciono** — Ako trebaju backup ili analiza u drugom alatu

## Baza podataka struktura

Tablica `pr_comments` sadrži:

- **PR info**: `pr_number`, `pr_title`, `pr_author`, `pr_created_at`, `pr_url`
- **Komentar**: `comment_author`, `comment_date`, `comment_path`, `comment_line`, `comment_text`, `comment_url`, `comment_diff_hunk`
- **Akcije**: `viewed`, `status`, `priority`, `assigned_to`, `notes`
- **Timestamps**: `created_at`, `updated_at`

## Cron setup (opciono)

Za automatsko pokretanje svakih 24h:

```bash
# Linux/Mac - dodaj u crontab
0 2 * * * cd /path/to/project && python export_pr_comments.py >> /var/log/pr_tracker.log 2>&1
```

## Dashboard

Otvori `dashboard.html` u browseru da vidim live podatke iz Supabasea.

**Što dashboard omogućuje:**
- ✅ Real-time prikaz svih komentara
- ✅ Inline editing — direktno promijeni status ili prioritet (bez reloada)
- ✅ Live filtri — po statusu, prioritetu, autoru, tekstu
- ✅ Stats — brojčevi ukupnih, otvorenih, riješenih komentara
- ✅ Auto-refresh svakih 30 sekundi

**Statusi:**
- **Otvoreno** — trebam raditi na tome
- **Riješeno** — done, action je odradjen
- **Odbijeno** — ignoriram, nije relevantno

**Prioriteti:**
- **Nisko** — može čekati
- **Srednje** — trebam raditi sada
- **Visoko** — urgent

## Greške & troubleshooting

**"SUPABASE_URL i SUPABASE_ANON_KEY moraju biti postavljeni"**
- Provjeri da li `.env` datoteka postoji i ima ispravne kredencijale

**"gh: command not found"**
- Instaliraj GitHub CLI: `brew install gh` (macOS) ili `choco install gh` (Windows)

**Duplikati u bazi?**
- Skriptu koristi `upsert` na `comment_url` - ako je URL isti, komentar se ažurira

**Dashboard se nije učitao u browseru?**
- Provjeri da su kredencijali u `dashboard.html` ispravni (trebam biti isti kao u `.env`)
- Provjeri CORS — Supabase trebam dozvoliti zahtjevu s lokalnog hostinga
