Скопируйте `issue.example.json` в `content/YYYY-MM-DD.json`, замените поля. В `body` доступны блоки:
`<article class="lead">` (главный, фото слева), `<article class="feature">` с `<div class="cols">`, `<div class="grid">` с `<article class="note">`,
`<section class="rubric">` (рубрики), `<p class="kicker">`, `<p class="op">` (мнение редакции), `<p class="src">` (источники), `<ul class="facts">`.
Пути к картинкам: `{{ROOT}}assets/img/имя.jpg`.

Порядок рубрик в номере (пример — `issue.example.json`): Главное → Большой материал → Статья дня с arXiv → Цифра дня → заметки (grid) →
Наука в России + Хорошие новости из России (grid из двух `note`) → Кадр дня (`rubric` с `figure`) → ИИ‑инструмент дня → Мысленный эксперимент →
Идея дня → Что почитать и посмотреть. «Было/стало» (только понедельник) — `<section class="rubric">` с `<p class="kicker">Было/стало</p>` и списком
`<ul class="facts"><li><strong>Было:</strong> … → <strong>Стало:</strong> … <a>источник</a></li></ul>`, ставить после «ИИ‑инструмента дня».
В `items` для каждого материала указывать `rubric`, `title`, `source`, `event_date`.
Не добавлять в шаблоны ссылки на `issues.json` для читателя — файл служебный.

Навигация генерируется `build.py`: ссылки на архив и PDF в теле номера не добавлять (они в шапке), внизу/вверху — только ←/→ между номерами.
