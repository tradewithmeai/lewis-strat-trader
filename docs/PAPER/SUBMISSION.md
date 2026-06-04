# Getting the paper to a public, citable record

**Goal:** a permanent, timestamped, citable version of the undergraduate paper
online (persistent ID / DOI). Sequenced lowest-friction first. The citable record
needs only a *persistent identifier* — not a typeset PDF — so the early steps need
no toolchain at all.

Source of truth stays `docs/PAPER/UNDERGRAD_PAPER.md`. The submission artifacts in
`docs/PAPER/submission/` are generated from it (regenerate command at the bottom).

## Artifacts (already generated → `docs/PAPER/submission/`)
- **`paper.docx`** — open in Word / Google Docs, *export to PDF*. Zero-install path
  to a PDF for SSRN / Zenodo.
- **`paper.tex`** — LaTeX source for arXiv. Compile on **Overleaf** (free, browser,
  no local install): New Project → Upload `paper.tex`.
  - **Compile with XeLaTeX, not pdfLaTeX.** The paper uses unicode (en-dashes, ×,
    ≈, "bp"); pdfLaTeX chokes on these. Overleaf: *Menu → Settings → Compiler →
    XeLaTeX*.
  - References are kept as a **formatted list**, deliberately *not* wired into
    BibTeX `\cite` machinery — that is a journal-submission concern, not needed for
    a citable record.

## Route — do in this order

### 1. OSF — register the pre-registration (free, ~15 min, no toolchain)
- Account at osf.io → New Project.
- Add `docs/PAPER/PREREGISTRATION.md` (and Amendment 1).
- Create a **Registration** (frozen, timestamped, gets a DOI). This independently
  strengthens the paper's "pre-committed / exploratory" claim.
- Optionally host the frozen signal manifest + code pointer here too.

### 2. Zenodo — mint a DOI (free, ~10 min)
- zenodo.org → log in with GitHub.
- Either link the repo and cut a GitHub **release** (Zenodo auto-mints a DOI for
  that release), or upload the paper PDF directly.
- Fill metadata: title, author(s), abstract, license.

### 3. SSRN — finance-native working-paper home (free)
- Author account at ssrn.com → upload the PDF (from `paper.docx`).
- JEL codes: **G14** (market efficiency / event studies), **G12** (asset pricing),
  **C58** (financial econometrics). Keywords: event study, realised volatility,
  social media, cryptocurrency, Bitcoin.

### 4. arXiv — q-fin (later; one real hurdle)
- Upload `paper.tex` source (compiled on Overleaf first to confirm it builds).
- Category: **q-fin.ST** (Statistical Finance) primary; cross-list **q-fin.TR**
  (Trading & Market Microstructure).
- **Endorsement hurdle:** first-time q-fin submitters usually need an endorsement
  from an existing q-fin author, or must submit from an affiliated-institution
  email. This is the step that can block — line it up in advance; don't let it gate
  the OSF/Zenodo/SSRN win above.
- Compile reminder: XeLaTeX.

### 5. Journal (optional, much later)
- Genuine peer review. Plausible homes: *Finance Research Letters*, *Journal of
  Behavioral and Experimental Finance*, *Digital Finance*. This is where full
  formatting + BibTeX become worth the effort.

## Human-only decisions — these gate everything (I cannot make them)
1. **Author name + affiliation.** "Independent researcher" is an accepted
   affiliation for preprints. Goes into `paper.tex` `\author{}`, the `.docx`, and
   the Reproducibility & disclosure block.
2. **AI-assistance disclosure wording.** Standard policy across arXiv / SSRN /
   journals: AI systems are **not** authors; the human is the author and the
   AI role is disclosed. The paper already carries a disclosure sentence in
   *Reproducibility & disclosure* — confirm or adjust. Suggested wording:
   > "This research was carried out with substantial AI-assisted coding and
   > analysis under the direction of the author(s). AI systems are not authors.
   > The complete decision-and-execution record is preserved in the project
   > work-log (`docs/WORKLOG.md`)."
3. **License** — for Zenodo / the repo (e.g. CC-BY-4.0 for the paper text,
   MIT/Apache-2.0 for the code).
4. **Which venues** to actually post to (all of the above, or a subset).

## Regenerate the artifacts (after editing the `.md`)
```bash
uv run --with pypandoc-binary python -c "
import pypandoc
md = open('docs/PAPER/UNDERGRAD_PAPER.md', encoding='utf-8').read()
body = md[md.index('## Abstract'):]
meta = '''---
title: \"Posts as Events: Intraday Cryptocurrency Volatility Around a Head of State's Social-Media Communications\"
author: \"[Author name and affiliation — to complete]\"
date: \"June 2026\"
---

'''
pypandoc.convert_text(meta+body,'latex',format='md',outputfile='docs/PAPER/submission/paper.tex',extra_args=['--standalone'])
pypandoc.convert_text(meta+body,'docx', format='md',outputfile='docs/PAPER/submission/paper.docx')
"
```
(`pypandoc-binary` bundles the pandoc executable — no system install needed.
Compile reminder: XeLaTeX.)
