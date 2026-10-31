# Cloudflare Workers через GitHub

Владелец выбрал GitHub-деплой 31 октября 2026. Это заменяет прежний план Pages
Direct Upload. Экран **Set up your application** с полями **Build command** и
**Deploy command** относится к Workers. Используем Workers Static Assets.

## Что собирается где

Mac формирует сайт и PDF закреплённым Chromium, проверяет их и сохраняет полный
неизменяемый снимок в `previews/`. Затем `rp release` экспортирует читательские
файлы в `public/`; контрольные суммы — в `public.release.json` рядом с каталогом.

Cloudflare забирает файлы из GitHub, проверяет их через Node и загружает готовую
статику. Python, браузер, OpenAI API, Docker и секреты модели ему не нужны.
В `wrangler.jsonc` настроен только `./public`, без серверного приложения.

В public входят страницы RU/EN/JA, архив, статьи, шесть PDF текущих выпусков,
локальные изображения/шрифты/лицензии, RSS, sitemap, robots.txt и страница 404.
Исходные JSON, отчёты, снимки PDF-страниц и печатные HTML туда не входят.

## Точные настройки экрана Cloudflare

| Поле | Значение |
|---|---|
| Application / Worker name | `pravdareplikanta` |
| Repository | `vanderlvoff/pravdareplikanta` |
| Production branch | `main` |
| Build command | `npm run check:public` |
| Deploy command | `npx wrangler deploy` |
| Root directory | корень репозитория, пустое поле или `/` |
| Environment variable | `NODE_VERSION=22.16.0` |

Wrangler закреплён в package.json/package-lock.json. Не нужно задавать Python
build command, устанавливать Playwright в Cloudflare или вводить API-ключи модели.
Cloudflare Workers Builds автоматически создаёт собственную авторизацию загрузки.
Поля и значения следует сохранять после того, как public/ и конфигурация попадут
в GitHub. Кнопка **Deploy** — окончательное подтверждение первой публикации.

После включения Git-интеграции push в production-ветку запускает деплой
автоматически. Редакторский просмотр выполняется перед отправкой нового public/:
обновление исходных data/latest само по себе не перегенерирует готовые страницы.

## Подготовить первый релиз локально

```sh
rp build --publication --issue 2026-10-31 --content-dir content/technical \
  --archive-issue content/technical/2026-10-30.json --pdf \
  --output previews/publication-2026-10-31-2
rp verify --issue 2026-10-31 --output previews/publication-2026-10-31-2
rp release --snapshot previews/publication-2026-10-31-2 --output public
rp preview --output public
npm run check:public
```

`--publication` допускает только approved/published номера, убирает служебные
плашки и разрешает индексацию читательских страниц. Эта команда ничего не
загружает. Обычный build остаётся локальным preview с noindex. `rp release`
требует полноценную PDF-сборку и успешную проверку всего снимка; существующий
каталог и отчёт не перезаписываются. Проверки на Cloudflare также отвергают
изменённые/лишние/недостающие файлы и неподходящие статусы.

Следующие выпуски сначала экспортируйте в новый каталог, например
`--output previews/public-next`; просмотрите его через rp preview, затем замените
отслеживаемые public/ и public.release.json этим полным комплектом. Предыдущий
комплект сохраняйте до успешной загрузки и фиксируйте изменения в Git.
Публичная папка намеренно находится в Git, а previews/ остаётся исключённым.

## Проверить конфигурацию без загрузки

```sh
npm ci
npm run check:public
npx wrangler deploy --dry-run --outdir previews/wrangler-dry-run
```

Для проверки настоящих правил маршрутизации используйте `npm run dev:public`.
Неизвестные пути возвращают 404, а не главную страницу приложения. RSS имеет
application/rss+xml; технические workers.dev/версионные адреса получают noindex
через _headers. Canonical и sitemap используют https://repravda.com.

## Домен и восстановление

После первой успешной загрузки откройте Worker → Settings → Domains & Routes →
Add → Custom Domain и подключите `repravda.com`. DNS/регистрация домена и права
на него настраиваются владельцем отдельно; настройка canonical не подтверждает DNS.

При неудачной сборке/проверке Cloudflare не выполняет Deploy command и предыдущая
версия продолжает работать. Для отката опубликованной версии используйте историю
Deployments в Worker либо верните прошлый комплект public/ и public.release.json
из Git и запустите новый деплой. Старые локальные проверенные снимки сохраняйте.

Документация Cloudflare:
[Workers Builds](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/),
[Static Assets](https://developers.cloudflare.com/workers/static-assets/binding/),
[HTML routing](https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/).
