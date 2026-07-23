# 블로그 포스트 통합 대시보드

WikiDocs 14개 블로그와 Tilnote 1개 블로그의 모든 공개 포스트 제목·주소를 한 테이블에 모으고, GitHub Pages 대시보드로 보여줍니다.

## 공개 데이터

- 플랫폼, 블로그명, 블로그 주소
- 마스킹된 계정
- 포스트 제목, 주소, 발행 시각, 최초 수집 시각
- JSON 및 UTF-8 BOM CSV

원본 이메일과 WikiDocs 인증 토큰은 공개 파일에 저장하지 않습니다. 토큰은 GitHub Actions의 `WIKIDOCS_BLOGS_JSON` 저장소 Secret으로만 관리합니다.

## 자동 갱신

`.github/workflows/update-and-deploy.yml`이 매시 17분(UTC 기준)에 실행됩니다. 최초 실행은 전체 글을 수집하며, 이후 실행은 기존 글 ID를 기준으로 새 글만 증분 수집합니다. 데이터가 바뀌면 Actions 봇이 `data/posts.json`과 `data/posts.csv`를 커밋하고 GitHub Pages를 다시 배포합니다.

수동 실행은 저장소의 **Actions → Update posts and deploy dashboard → Run workflow**에서 할 수 있습니다.

## 로컬 실행

```bash
python -m pip install -r requirements.txt
python -m http.server 8000
```

수집기를 로컬에서 실행하려면 `WIKIDOCS_BLOGS_JSON` 환경 변수가 필요합니다. 인증값을 `.env`나 저장소 파일로 커밋하지 마세요.
