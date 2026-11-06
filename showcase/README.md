# November 2026 research showcase

The [final showcase package](2026-11-08/README.md), prepared on 6 November,
contains a one-page landscape poster, a title slide plus five content slides,
a 140-word abstract, editable PowerPoint supplements, and a 382-word group
speaking script with Q&A preparation. The PDFs are the primary submission files.

**The Tests Passed. The Grader Said No.** presents two findings from our local
AI security-repair audit: nine of twenty hidden-rule final submissions passed
the implemented tests but were rejected, and an acknowledged stop request did
not directly end the historical runner. It explains the limits of both findings.

Project team: **Imran Zakirov, Iosifova Nuriya, and Kramich Anna**.
Anna is also the mentor and an active project participant.

Download the [complete ZIP](Zakirov_Iosifova_Showcase_2026-11-08.zip), or use
the individual PDFs linked in the package README. One team member submits for
the project by **8 November 2026, 12:00 noon, Bishkek time (UTC+6)**, as stated
in the organizer checklist supplied by the user.

To rebuild from the repository root with the bundled workspace Python:

```sh
python -B -m showcase.build_showcase
python -B -m showcase.export_pdf
python -B -m showcase.validate_showcase
python -B -m showcase.package_showcase
```

The PDF exporter uses ReportLab. Submission status: **NOT_SUBMITTED**.
A real timed rehearsal is still pending; the group script targets 3:40–3:45
within the four-minute limit.
