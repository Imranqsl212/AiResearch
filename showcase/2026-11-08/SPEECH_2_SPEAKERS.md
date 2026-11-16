# Speech for two speakers · 4 minutes

**Speakers:** Imran Zakirov and Iosifova Nuriya. Kramich Anna is named as mentor and team member.
**Target:** about 3:45 at a calm pace (~450 words). The organizer switches slides — say **"Next slide, please."**

---

### Title slide · IMRAN · 0:00–0:25

Imagine you take a test, answer every question correctly… and your teacher still gives you a fail. Unfair, right? That is what happened to an AI in our experiment.
I'm Imran Zakirov, this is Iosifova Nuriya, and our mentor and teammate is Kramich Anna. Our project is called "The Tests Passed. The Grader Said No."
*Next slide, please.*

### Slide 1 — The question · IMRAN · 0:25–1:00

Today, AI agents can fix security bugs in code on their own. They work in a loop: the AI writes a fix, a checker tests it and says PASS or FAIL. Then the AI decides: stop, or try again?
We wanted to study that decision. But we quickly realized: if the score itself is wrong, we cannot judge the AI's choice. So first, we checked the checker.
*Next slide, please.*

### Slide 2 — The method · NURIYA · 1:00–1:35

We looked at forty saved sessions with one small AI model, Qwen, running on a local computer, across five types of Python security tasks.
Our checker had two steps. Step one: run the tests. Step two — here is the twist — in twenty sessions, we added a hidden rule: reject everything. The AI could not see it. We wanted to imitate a task with no solution.
*Next slide, please.*

### Slide 3 — First finding · NURIYA · 1:35–2:15

Each block here is one of those twenty sessions. In nine of them, the final code passed all our tests — and still got FAIL.
To be fair, our tests were limited, so passing them does not prove the code is fully secure. But it shows that the score and the test results can tell two different stories. If you only looked at the score, you would blame the AI.
*Next slide, please.*

### Slide 4 — Second finding · IMRAN · 2:15–3:00

Then we found a second surprise, about stopping. In fourteen sessions, the AI got a PASS and immediately said: "I'm done, stop." Perfect!
But the session did not end. In thirteen of them, it kept running for about two more minutes — two minutes eight seconds in the median case. One more ended by timeout.
And in that time, the AI made zero new repair attempts. So the AI was not stubborn. Our old software simply waited for one more extra signal. Again, the problem was in the measuring tool.
*Next slide, please.*

### Slide 5 — What we learned · NURIYA · 3:00–3:45

Our biggest challenge was separating the AI's behavior from mistakes in our own tools.
So we fixed what we could: now every check is recorded, and we tested that the new system stops right away when the AI asks.
Next, we want independent review of our tasks, and a fair comparison: the same code, but a true PASS versus a false FAIL. Our small pilots are only a start.
Our main lesson is simple: before you judge the AI, check the grader. Thank you!

---

## Tips

- Say the numbers slowly: **"nine out of twenty"**, **"two minutes, eight seconds"**, **"zero"**.
- Short pause after the hook in the first line and after "check the grader."
- If you hear "30 seconds", Nuriya skips to: *"Our main lesson is simple…"*
- Quick Q&A answers are in [TALK_AND_QA.md](TALK_AND_QA.md#ответы-для-минуты-qa) (e.g. *Who wrote the hidden rule? — Our team did.*).
