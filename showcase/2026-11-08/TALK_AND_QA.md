# Выступление и подготовка к вопросам

Групповой лимит — **4 минуты**, затем **1 минута Q&A**. Цель для этой речи —
**3:40–3:45 с паузами и переключениями**. Это расчётный план, а не проведённая
репетиция. Обязательно прочитайте вслух с таймером.

Слайды переключает организатор. Фразу **“Next slide, please.”** произносим
пять раз — после титула и первых четырёх содержательных слайдов.

Все трое указаны как участники проекта; Kramich Anna также ментор. Распределение
речи ниже — предложение для выступления, а не утверждение об индивидуальном
вкладе в исследование.

## Групповой текст на английском

### Title · Imran Zakirov · 0:00–0:25

Imagine passing a teacher’s tests and still receiving a fail. Something similar
happened in our AI experiment. We are Imran Zakirov, Iosifova Nuriya, and Kramich
Anna, who is also our mentor. Our project is called “The Tests Passed. The Grader
Said No.” Next slide, please.

### Slide 1 · Imran Zakirov · 0:25–0:55

Our starting question was: when should an AI stop trying to repair code?
The AI saw a small security problem in Python, suggested a fix, and received
PASS or FAIL. It could stop or try again. This matters because people use such
scores to judge AI-written code. But first, could we trust our own checker?
Next slide, please.

### Slide 2 · Iosifova Nuriya · 0:55–1:30

We reviewed forty saved sessions from one local AI model, Qwen, across five
small task types. We compared the final code’s test result with its final score.
In twenty sessions, our team had added a hidden rule: reject every solution.
The AI could not see it. We intended this to represent an unavailable condition.
But rejecting everything did not prove that the coding task itself was impossible.
Next slide, please.

### Slide 3 · Iosifova Nuriya · 1:30–2:00

In nine of those twenty sessions, the final code passed our written tests but
still received FAIL. Each block represents one session with the hidden rule.
This does not mean nine solutions were completely secure: our tests were limited.
It means the final score could disagree with the implemented tests.
Next slide, please.

### Slide 4 · Kramich Anna · 2:00–2:50

We found another surprise. In fourteen repairable sessions, the AI requested
termination immediately after a PASS. The software did not end on that request
alone. Thirteen sessions later ended without timeout; their median wait was about
two minutes and eight seconds. One ended by timeout and is excluded from that
median. No further repair attempts were logged. A controlled software test
confirmed the extra decision step. This was about finishing after a PASS,
not evidence that the AI refused to give up. Next slide, please.

### Slide 5 · Kramich Anna · 2:50–3:40

The challenge was separating AI behavior from our measuring software. Missing
old step results also limited what we could conclude. We now record every check,
and a regression test confirms that the new collector stops immediately on a
termination request. Small follow-up experiments remain exploratory. Next, we
need independent task review and broader comparisons of truthful PASS versus
false FAIL. Our lesson: before judging the AI, check the grader. Thank you.

## Если выступают только два студента

**Imran:** титул, слайды 1 и 4. **Nuriya:** слайды 2, 3 и 5.
Анна остаётся указана как ментор и участник проекта. Групповой лимит — 4 минуты.

Если фактически выступает один человек, лимит — **3 минуты**: сократите титул
до названия и имён; на слайде 2 оставьте числа и объяснение скрытого правила;
на слайде 4 оставьте «14 после PASS, медиана 2:08 для 13, один timeout,
новых исправлений не было»; на слайде 5 оставьте главный вывод и следующий шаг.
Не ускоряйте чтение в ущерб понятности.

## Простое объяснение по-русски

Мы дали ИИ маленькие задачи: исправить ошибку безопасности в коде. Он отправлял
решение нашей программе-проверяющему и получал PASS («прошёл») или FAIL
(«не прошёл»). Мы хотели понять, когда он продолжает исправления, а когда
заканчивает.

Потом проверили самого проверяющего. В 20 из 40 старых запусков **мы сами**
добавили скрытое правило: «не принимать никакое решение». В 9 из этих 20
итоговый код прошёл наши ограниченные тесты, но всё равно получил FAIL.
Поэтому такая оценка сама по себе не доказывает, что ИИ плохо исправил код.
Пройти наши тесты также не значит быть полностью безопасным.

Нашли и вторую проблему измерения. В 14 других случаях ИИ запросил завершение
сразу после сообщения PASS. Программа не завершалась по одному этому запросу.
Для 13 случаев без timeout середина ряда задержек — около 2 минут 8 секунд;
один случай с timeout посчитан отдельно. Новых попыток исправления после запроса
в логах нет. Это не история «ИИ не умеет сдаваться»: здесь он уже получил PASS.

Главный вывод: прежде чем оценивать поведение ИИ, нужно проверить программу,
которая ставит ему оценки и записывает, когда он закончил. Мы улучшили запись
проверок и проверили немедленное завершение в новом сборщике. Следующий большой
эксперимент ещё требует независимой проверки задач.

## Ответы для минуты Q&A

**Who wrote the hidden rule?** Our research team did. It was part of our checker,
not a secret rule created by the AI.

**Why add a rule that rejects everything?** It represented an unavailable condition.
Our audit showed that this does not prove the underlying coding task impossible.

**Were the nine solutions secure?** They passed our limited tests. We did not prove
security in every situation.

**Did the false FAIL make the AI worse?** These historical records cannot establish
that. Our small follow-up comparisons remain exploratory.

**What does “two minutes and eight seconds” mean?** It is the rounded median time
from the first acknowledged termination request to final stop in thirteen historical
sessions without timeout. All had received PASS before requesting termination.
The fourteenth ended by timeout and is reported separately.

**Was the AI still trying to fix the code during that delay?** No further repair
attempts were logged. The runner took another decision step. We do not have the
exact internal provider requests from that interval.

**Did you prove the new version saves two minutes?** No. The controlled test checks
how stopping works; it does not measure how much time an alternative runner would
have saved in the old sessions.

**What have you completed?** A reproducible audit of saved runs, better check logs,
a controlled test of the old stopping mechanism, and a regression test for immediate
termination in the new collector. The larger study is still unfinished.

**What is a benchmark?** A set of tasks and scoring rules used to evaluate a system.

**Did you use AI to help?** Yes. Codex assisted with analysis code, drafting,
editing, and artifact checks. Human authors remain responsible for reviewing
the evidence and claims.

**What did each person do?** Each person should name only their own confirmed
contribution. Speaking assignments do not establish research contributions.

## Репетиция

1. Откройте PDF презентации и включите таймер; репетируйте всей выступающей командой.
2. Проговорите весь текст, включая передачи слова и просьбы переключить слайды.
3. Если получилось больше 3:45, сократите пояснение о первоначальной цели скрытого
   правила на слайде 2 и часть про controlled test на слайде 4. Сохраните знаменатели
   и оговорку, что задержки возникли после PASS.
4. На сигнал «30 секунд» завершите текущую мысль и переходите к выводу на слайде 5.
5. Проверьте камеру, микрофон, тихое место и соединение. Камера должна быть включена.

Репетиция и отправка материалов пока **не подтверждены**. Не отмечайте их как
выполненные, пока действительно не проведёте репетицию и не отправите комплект.

## Источники для подготовки, не для чтения вслух

- Основной подсчёт: `paper/artifacts/results.json`, разделы `main` и `policy_rejected`.
- Остановка после PASS: `analysis/HISTORICAL_TERMINATE_LATENCY_20261104.md`.
- Контроль механизма: `analysis/STOP_CONTRACT_CONTROL_20261104.md`.
- Новое немедленное завершение: `tests/test_v1_collector.py`,
  `test_terminate_tool_stops_without_another_adapter_decision`.
- Полная интерпретация и ограничения: `paper/final.md`.
