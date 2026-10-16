# Journal shortlist for the historical exploratory audit

Rechecked 16 October 2026 against **official journal and publisher pages**. This
shortlist concerns [`final.md`](final.md): a 40-episode, five-family audit of one
local agent and a benchmark acceptance veto, with an eight-episode AEAD pilot
and a later 30-episode corrected-oracle pilot reported separately. It is an
**exploratory measurement paper**. Neither pilot is pooled with the 40 main
episodes or admitted to the prospective study. Fit below is an editorial
judgment, not a prediction of acceptance.

| Venue and article type | Why this paper may fit | Current submission and data requirements; local gap |
| --- | --- | --- |
| **1. Software Quality Journal — Original Paper.** [Scope](https://link.springer.com/journal/11219/aims-and-scope); [instructions](https://link.springer.com/journal/11219/submission-guidelines). | Its stated remit includes software measurement, testing, and quality assurance. Frame the result as an audit of a repair evaluator's raw test versus acceptance gate, with narrow evidence limits. | [Instructions](https://link.springer.com/journal/11219/submission-guidelines) call for a 150–250-word abstract, 4–6 keywords, editable source, author/declaration details, and a Data Availability Statement. The journal-specific format rule still requires `sn-jnl` LaTeX, while a later generic text section says Word is accepted; resolve this conflict in the submission portal or with the editorial office before conversion. The current abstract is 237 words, and the manuscript has **six** keywords. The historical data and archives are already public at [revision `37074c19`](https://github.com/Imranqsl212/AiResearch/tree/37074c198237ade67eb76921333b2835d329c863), but the exact journal data statement and privacy review remain pending. |
| **2. Empirical Software Engineering — Research Article.** [Scope](https://link.springer.com/journal/10664/aims-and-scope); [instructions](https://link.springer.com/journal/10664/submission-guidelines). | Its scope explicitly includes empirical verification/validation, quality assurance, and AI applied to software engineering; it welcomes studies that can be replicated or expanded. The methodological lesson may fit if the limited local cohort and benchmark-specific contribution stay explicit. | [Instructions](https://link.springer.com/journal/10664/submission-guidelines) require editable `.docx` or LaTeX source, a 150–250-word abstract, 4–6 keywords, declarations, and a Data Availability Statement for original research. The existing DOCX is an editable starting point. The historical data and archives are already public at [revision `37074c19`](https://github.com/Imranqsl212/AiResearch/tree/37074c198237ade67eb76921333b2835d329c863); author approval of the precise data statement and privacy review for a journal supplement remain pending. |
| **3. Journal of Systems and Software — regular paper.** [Official journal description](https://shop.elsevier.com/journals/journal-of-systems-and-software/0164-1212); [Guide for Authors entry](https://www.sciencedirect.com/science/journal/01641212). | The journal lists software testing/validation, AI in software engineering, metrics, and empirical methods, and welcomes negative results. The hidden-veto finding could be presented as new knowledge about evaluating repair agents. | Its [official description](https://shop.elsevier.com/journals/journal-of-systems-and-software/0164-1212) calls for evidence supporting claims and contribution beyond a specific domain. Its Open Science initiative can review materials after acceptance when authors opt in; when materials cannot be shared, authors should state that explicitly. The journal-specific Guide for Authors was not accessible in this check (ScienceDirect returned 403), so precise file, abstract, and data-statement rules must be checked in the live submission portal before preparing a JSS version. A single local model and five families may be too narrow for the general contribution this venue requests. |

## Shared work before choosing a venue

1. **Author decision:** choose one journal and approve the final author order,
   affiliations, corresponding author, contributions, funding, interests, and
   any required disclosure of manuscript-generation assistance. The [Springer
   EMSE](https://link.springer.com/journal/10664/submission-guidelines) and
   [SQJ](https://link.springer.com/journal/11219/submission-guidelines) instructions
   require author accountability and relevant declarations.
2. **Evidence statement and journal deposit:** the [public data revision
   `37074c19`](https://github.com/Imranqsl212/AiResearch/tree/37074c198237ade67eb76921333b2835d329c863)
   already contains the historical raw trajectories, original archive,
   sanitized candidate, code, and derived tables. Public GitHub availability
   does not certify privacy review or make those files an approved journal
   supplement. Verify the inputs from a fresh checkout, approve a Data
   Availability Statement describing that actual public route, and review any
   separate deposit before submission. The transformed candidate supports a
   table-only replay but does not preserve the original-byte hash chain. Both
   [EMSE](https://link.springer.com/journal/10664/submission-guidelines) and
   [SQJ](https://link.springer.com/journal/11219/submission-guidelines) require
   a Data Availability Statement for original research.
3. **Manuscript adaptation:** keep the 9/20 test–gate discordance as a finding
   about this evaluator, preserve all small-sample and source-capture limits,
   retain 4–6 keywords for a Springer submission, convert numbered in-text
   citations to author–year citations with an alphabetized reference list,
   and format the current review PDF/DOCX for the chosen venue. A separate
   [author–year draft](venue_author_year_draft.md) makes the citation conversion
   reviewable without replacing the numbered master manuscript. The
   [SQJ](https://link.springer.com/journal/11219/submission-guidelines) and
   [EMSE](https://link.springer.com/journal/10664/submission-guidelines)
   instructions say their reference lists should contain cited works published
   or accepted for publication. The publisher's
   [preprint guidance](https://www.springernature.com/cn/researchers/the-researchers-source/open-science-blogpost/four-things-to-know-about-springer-natures-new-preprint-policy/16747974)
   explicitly permits preprint citations, so those entries are not automatically
   disallowed; identify them honestly and prefer a verified published version
   where one exists. Do not recast
   descriptive guidance/feedback contrasts as causal estimates or treat the
   later prospective pilots as part of the historical result.

**Suggested order:** SQJ for the most direct quality-measurement framing, EMSE
for a stronger empirical-methods framing with a simpler DOCX submission route,
then JSS if the authors can articulate a broader software-engineering lesson.
The author must make the final venue and data-access decisions; none of these
venues has been contacted or has reviewed the manuscript.

## Current guideline check — 16 October 2026

The official [SQJ instructions](https://link.springer.com/journal/11219/submission-guidelines)
still contain a format conflict: their journal-specific section says the
submission **must use** the Springer Nature `sn-jnl` LaTeX class, while a
later general section says Word files are accepted. Ask the submission portal
or editorial office which rule applies before converting this venue-neutral
DOCX. The same page describes single-blind review, a 150–250-word abstract,
4–6 keywords, and a required declaration section. It explicitly allows an
unaffiliated author to give city and country. Its current page says there is
no submission or ordinary publication fee, with optional paid open access.

The official [EMSE instructions](https://link.springer.com/journal/10664/submission-guidelines)
accept an editable `.docx` or LaTeX source, describe single-blind review, and
require a Data Availability Statement for original research. If data cannot be
public, the statement must give the actual access conditions. Both journals'
instructions say substantive LLM use should be documented in **Methods** and
the human author remains responsible for the final text. The current draft
discloses Codex assistance in Methods and Acknowledgments; obtain the author's
approval of that wording and the other declarations for the chosen venue.
Both journals require author–year in-text citations and an alphabetized
reference list, so the current numbered citations need a venue-specific
conversion. Their published instructions describe single-blind review; an
anonymous copy may be retained but is not required by those instructions.
Neither venue is selected or contacted by this check.
