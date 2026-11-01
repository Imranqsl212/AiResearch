# Understand the project in one minute

## По-русски

ИИ исправляет небольшую ошибку безопасности в коде. Наш проверяющий запускает
тесты и говорит ему PASS или FAIL. После FAIL ИИ может переписать код и
попробовать снова. Мы изучаем, можно ли доверять такому ответу и как он
влияет на следующую попытку.

В 9 из 20 исторических запусков специальной группы **итоговый код прошёл
наши тесты**, но проверяющий всё равно сказал FAIL. Причина — скрытое правило,
которое мы сами добавили. ИИ его не видел. Это доказывает противоречие в
нашем измерении, а не полную безопасность кода или вред от ложного ответа.

Один реальный пример: в задаче про одноразовое значение для шифрования
итоговый код прошёл наши короткие тесты, а скрытое правило всё равно выдало
FAIL. Тесты были ограничены и не доказывают безопасность такого кода.

## In English, for the talk

We asked one AI system to fix small safety mistakes in code. After each fix,
our checker tested it and sent PASS or FAIL; the AI could then stop or try
again. We study how trustworthy that feedback is.

We reviewed **40 saved runs**. In 20 of them, our checker had an extra
“no” rule. In **9 of those 20**, the final code passed our written tests,
but the checker still said FAIL. **We wrote that extra rule**; the AI did
not see it.

For example, in one saved encryption task, the final code passed our small
test for a one-time value, but the hidden rule still returned FAIL.

Passing our small tests does **not** prove the code safe in every situation.
The old runs also cannot show whether the wrong message made the AI change a
good fix. Our paired follow-up starts two copies from the same checked code:
one hears true PASS, the other hears false FAIL. Small exploratory pilots have
used this idea, but the larger main study has no accepted runs yet.

**Remember:** Before judging the AI, check the grader.

## If someone asks

**Who made the extra rule?** Our research team put it in the checker.

**Were the nine fixes definitely safe?** No; they passed only our tests.

**Did the wrong score make the AI worse?** The old runs cannot answer that.
Small pilots are exploratory; the main comparison is still pending.
