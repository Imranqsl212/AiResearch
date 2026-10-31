# Understand the project in one minute

## По-русски

Мы дали ИИ небольшие задачи: исправить проблемы безопасности в коде. В
9 из 20 запусков специальной группы итоговый код прошёл **наши тесты**, но
наша система проверки всё равно сказала FAIL. Причина — дополнительное
правило, которое мы сами добавили; ИИ его не видел. Это не доказывает, что
код полностью безопасен или что такой ответ испортил работу ИИ.

## In English, for the talk

We asked one AI system to fix small safety mistakes in code. Our checker
tested each suggested fix and told the AI PASS or FAIL.

We reviewed **40 saved runs**. In 20 of them, our checker had an extra
“no” rule. In **9 of those 20**, the final code passed our written tests,
but the checker still said FAIL. **We wrote that extra rule**; the AI did
not see it.

Passing our small tests does **not** prove the code safe in every situation.
We also do **not** know whether the wrong message made the AI change a good
fix. Our planned next test starts two copies from the same checked code:
one hears true PASS, the other hears false FAIL. We will compare what
happens next. That larger test has no accepted results yet.

**Remember:** Before judging the AI, check the grader.

## If someone asks

**Who made the extra rule?** Our research team put it in the checker.

**Were the nine fixes definitely safe?** No; they passed only our tests.

**Did the wrong score make the AI worse?** We do not know yet.
