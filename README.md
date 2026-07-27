# PostPulse · 블로그 포스트 통합 대시보드

WikiDocs 14개 블로그와 Tilnote 1개 블로그의 공개 포스트를 수집하고, 발행량·조회 흐름·당일 현황을 GitHub Pages 대시보드로 보여줍니다. 프런트엔드는 React, TypeScript, Vite, Tailwind CSS와 shadcn/ui 방식의 재사용 컴포넌트로 구성했습니다.

## 대시보드

- Figma 기반 콘텐츠 인텔리전스 UI
- 최근 14일 발행 차트와 당일 블로그별 발행량
- 블로그별 전체 글·당일 글·누적 조회·당일 조회 비교
- 전체 포스트의 검색, 플랫폼·블로그·날짜 필터, 정렬, 페이지네이션
- CSV 다운로드와 5분 간격 화면 자동 새로고침

## 공개 데이터

- 플랫폼, 블로그명, 블로그 주소
- 마스킹된 계정
- 포스트 제목, 주소, 발행 시각, 최초 수집 시각
- JSON 및 UTF-8 BOM CSV

원본 이메일과 WikiDocs 인증 토큰은 공개 파일에 저장하지 않습니다. 토큰은 GitHub Actions의 `WIKIDOCS_BLOGS_JSON` 저장소 Secret으로만 관리합니다.

## 자동 갱신

`.github/workflows/update-and-deploy.yml`이 매시 17분에 실행됩니다. 최초 전체 이력 수집 중 느리거나 실패한 Tilnote 페이지는 진행 상태를 `data/posts.json`에 체크포인트로 남기고 다음 실행에서 이어 받습니다. 전체 이력이 완성된 뒤에는 기존 글 ID를 기준으로 새 글만 증분 수집합니다. 데이터가 바뀌면 Actions 봇이 JSON과 CSV를 커밋하고, Node.js 프로덕션 빌드 결과인 `dist`만 GitHub Pages에 배포합니다.

수동 실행은 저장소의 **Actions → Update posts and deploy dashboard → Run workflow**에서 할 수 있습니다.

## 로컬 실행

```bash
npm install
npm run dev
```

프로덕션 빌드는 `npm run build`로 생성합니다. 수집기를 로컬에서 실행하려면 Python 의존성과 `WIKIDOCS_BLOGS_JSON` 환경 변수가 필요합니다. 인증값을 `.env`나 저장소 파일로 커밋하지 마세요.
