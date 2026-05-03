# 09. deleted 판정 추가

## 목적

전체 수집에서 사라진 항목을 `deleted`로 기록한다.

## 왜 뒤로 미루는가

잘못 구현하면 범위 수집에서 정상 데이터를 삭제된 것으로 오판할 수 있다.

## 정책

```text
--full-run 명시 시에만 deleted 판정
범위 수집에서는 deleted 판정 금지
--include-legacy 처리에서는 deleted 판정 금지
--data-type 일부 처리에서는 deleted 판정 금지
```

## 구현할 코드

```text
stage2_catalog/main.py
stage2_catalog/managers/catalog_writer.py
```

## 로직

```text
current_seen_keys = 이번 전체 실행에서 본 service key
previous_keys = 기존 crawl_latest.jsonl의 service key
deleted_keys = previous_keys - current_seen_keys
```

`--full-run`일 때만 `deleted_keys`를 `crawl_history.jsonl`에 append한다.

## 실행 명령

```powershell
python .\stage2_catalog\main.py --full-run
```

## 완료 기준

전체 수집에서 사라진 항목만 다음 상태로 기록된다.

```json
{
  "change_status": "deleted"
}
```

