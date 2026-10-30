# Editorial data contract (draft)

The canonical source of each issue is versioned JSON; the website and paper PDF are generated from that same data. The schema below is illustrative, not yet a formal JSON Schema.

```json
{
  "issue_id": "2026-10-29",
  "number": 1,
  "publication_date": "2026-10-29",
  "revision": 1,
  "status": "draft",
  "languages": {
    "ru": {
      "title": "Правда репликанта",
      "editorial_note": "Текст редакционной заметки",
      "articles": [
        {
          "id": "vla-evaluation",
          "slug": "vla-evaluation",
          "category": "news",
          "headline": "Тестовый заголовок",
          "dek": "Тестовый подзаголовок",
          "body": [{"type": "paragraph", "text": "Тестовый текст"}],
          "sources": [{"url": "https://example.org/source", "title": "Source", "published_at": "2026-10-28"}],
          "image_asset_id": null
        }
      ]
    },
    "en": {"title": "The Replicant Truth", "articles": []},
    "ja": {"title": "日本語題字（要承認）", "articles": []}
  }
}
```

## Validation rules

- `issue_id` ISO date; unique and stable. `revision` increments when correcting a public issue.
- `status` draft/review/approved/published. Publishing requires approved status.
- All language editions have identical article `id` for cross-language linking, but may contain editorially adapted text.
- Store sources per article (URL, title, source publication date, retrieval date when available).
- Use an allowlist for body block types (`paragraph`, `heading`, `quote`, `list`, `image`, `caption`), not arbitrary HTML from LLM output.
- HTML escaping is mandatory. Images are separately reviewed and stored in `assets/`.
- Missing translation, article citation, or license metadata should be surfaced in a validation report; the editorial policy decides whether publication is blocked.
- The example has intentionally incomplete EN/JA content and must fail full tri-language publishing validation.
- Use stable UTF-8 and language-specific font stacks for Cyrillic, Latin and Japanese.

## Weather snapshot

An optional issue-level `weather` object is shared across languages. Its date must
match `publication_date`. See [WEATHER.md](WEATHER.md) for fields and workflow;
the sample issue contains a complete saved forecast.

## Print page assignment

`print_page` remains an optional positive integer (default 1) for compatibility
with older JSON. Automatic pagination ignores this hint. Articles flow in section
order (news, then analysis) across as many A4 pages as needed. Font sizes stay fixed;
clipping and overlaps still reject the build. See [PRINT.md](PRINT.md).

## Prepared daily feeds

The external daily schema (`schema_version: 1.0`, issue_id `daily-YYYY-MM-DD`) is
accepted by `rp import`, which converts it to this internal issue schema.
`Edition.issue_title` retains the external issue title separately from the masthead.
See [DAILY_IMPORT.md](DAILY_IMPORT.md) for lossless editorial section mapping and
source validation.

Edition-level `weather` overrides the issue fallback forecast, with the same
validated snapshot schema and matching publication date. See WEATHER.md.
