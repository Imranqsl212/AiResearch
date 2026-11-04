# Выступление и подготовка к вопросам

Основной вариант рассчитан на группу: **до 4 минут**, целевой финиш — **3:45**.
Это план времени, а не запись проведённой репетиции. Прочитайте вслух с таймером.
Слайды переключает организатор; произносите **“Next slide, please.”**

Имена сохранены в написании, которое вы прислали. Анна указана как ментор
и участник проекта. Ниже предложено распределение речи; оно не является
заявлением об индивидуальном вкладе в исследование.

## Групповой текст на английском

### Title · Imran Zakirov · 0:00–0:25

Imagine fixing a coding exercise, passing the teacher’s tests, and still receiving a fail.
That is the contradiction we found in our AI experiment. We are Imran Zakirov and
Iosifova Nuriya, working with our mentor and project contributor, Kramich Anna.
Next slide, please.

### Slide 1 · Imran Zakirov · 0:25–0:55

Our starting question was: when should an AI stop trying to repair code?
The AI saw a small security problem in Python, proposed a fix, and received PASS or
FAIL. It could then stop or try another version. This matters because people use
feedback to judge AI-written code. To understand those repeated attempts, we also
needed to check whether the feedback was trustworthy. Next slide, please.

### Slide 2 · Iosifova Nuriya · 0:55–1:35

We reviewed forty saved sessions from one local AI model across five small task types.
We compared two things: did the final code pass our written tests, and did the
benchmark accept it? In twenty sessions, our research team had added a hidden rule
that rejected every solution. It represented an unavailable condition, but it did
not actually prove the coding task impossible. The AI did not see that rule.
Next slide, please.

### Slide 3 · Iosifova Nuriya · 1:35–2:15

In nine of those twenty sessions, the final code passed the written tests but still
received FAIL. Each dot here represents one of the twenty sessions with that rule.
One example involved a value intended for one-time use during encryption. Its final
code passed our small tests, but our hidden rule still rejected it. Passing these
tests did not prove the code completely secure. The result was a disagreement
between the tests and the final score. Next slide, please.

### Slide 4 · Kramich Anna · 2:15–3:00

The hardest challenge was discovering what the records could actually prove.
We had final test results, but the old logs did not preserve the raw results of every
earlier check. We could not identify exactly which revisions followed misleading
feedback. This changed our lesson: validate the grader, save each check, and explain
the limits of the tests. We improved the logging for later runs, but that cannot
recover evidence missing from the old records. Next slide, please.

### Slide 5 · Kramich Anna · 3:00–3:45

We have completed the historical audit, improved the logs, and run small exploratory
follow-ups. A fairer comparison starts two copies from the same checked code. One
receives a truthful PASS, the other a false FAIL. We compare their next steps and
whether the final version keeps the checked property. The larger study still needs
independent task review and broader testing. Our lesson so far is: before judging
the AI, check the grader. Thank you.

## Если выступают только два студента

Imran: титул, слайд 1 и слайд 4. Nuriya: слайды 2, 3 и 5.
Имя Анны остаётся на титуле как ментора и участника проекта. Остальной текст
не требует изменений. Лимит группы остаётся 4 минуты.

## Простое объяснение по-русски

Мы хотели узнать, когда ИИ прекращает исправлять код. Он отправлял решение
проверяющему и получал PASS или FAIL. Затем мы проверили самого проверяющего.

В 20 из 40 старых запусков было наше дополнительное скрытое правило:
«не принимать никакое решение». В 9 из этих 20 итоговый код прошёл записанные
тесты, но получил FAIL из-за этого правила. ИИ не видел правило. Поэтому
неудачная итоговая оценка сама по себе не доказывает, что ИИ плохо исправлял
код или не умел остановиться.

Тесты были маленькими: пройти их — ещё не значит быть полностью безопасным.
Также старые логи сохранили не все промежуточные результаты. Мы улучшили
логирование и начали пилоты: один и тот же проверенный код получает правдивое
PASS или ложное FAIL, после чего мы сравниваем действия агента. Большой
эксперимент ещё не завершён.

## Ответы для минуты Q&A

**Who wrote the hidden rule?** Our research team did. It was in our benchmark checker.
The AI could not see it.

**Why did you add it?** It represented an unavailable condition. The audit showed
that unconditional rejection does not prove a coding task impossible.

**Were the nine solutions secure?** They passed our limited tests. We did not prove
security in every situation.

**Did the wrong message make the AI worse?** The historical records cannot establish
that. Small paired pilots had mixed outcomes and remain exploratory.

**What is new here?** We provide a reproducible audit of this local checker and show
why its scores do not support strong conclusions about when the agent should stop.
We do not claim to be the first researchers to discover misleading feedback.

**What is a benchmark?** A set of tasks and scoring rules used to evaluate a system.

**Did you use AI to help?** Yes. Codex assisted with analysis code, drafting, editing,
and artifact checks. People remain responsible for reviewing the evidence and claims.

**What did each person do?** Answer using the contribution you can personally confirm.
The speaking assignments above do not establish who wrote particular code or text.

## Репетиция

1. Откройте PDF презентации и включите таймер.
2. Проговорите весь текст, включая передачу слова и просьбы переключить слайды.
3. Если получаются больше 3:45, сократите пример про шифрование на слайде 3.
4. На сигнал «30 секунд» переходите к последним двум предложениям слайда 5.
5. Проверьте камеру, микрофон и спокойное место для выступления.

При отправке материалов не отмечайте репетицию как выполненную, пока реально
не проведёте её с таймером.
