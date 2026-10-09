# vendor: 외부 정적 파일

인터넷 없이 동작하고 CSP를 `'self'`로 좁히려고(결정 W3) htmx와 Chart.js를 패키지에 넣는다. 모두 npm 레지스트리의 tarball에서 꺼낸 원본이며 수정하지 않았다.

| 파일 | 버전 | 원본 | 라이선스 | sha256 |
|---|---|---|---|---|
| `htmx-2.0.11.min.js` | htmx 2.0.11 | `https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.11.tgz`의 `package/dist/htmx.min.js` | 0BSD | `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717` |
| `LICENSE-htmx.txt` | htmx 2.0.11 | 같은 tarball의 `package/LICENSE` | 0BSD | `d3d2456f76414f2456104660ebd65aff1c04cd7966b942bdabd63f3cdb316a38` |
| `chart-4.5.1.umd.min.js` | Chart.js 4.5.1 | `https://registry.npmjs.org/chart.js/-/chart.js-4.5.1.tgz`의 `package/dist/chart.umd.min.js` | MIT | `48444a82d4edcb5bec0f1965faacdde18d9c17db3063d042abada2f705c9f54a` |
| `LICENSE-chartjs.md` | Chart.js 4.5.1 | 같은 tarball의 `package/LICENSE.md` | MIT | `41a84aa2caba645f966a18d9c2056b73e6d3a81d80bc0046bc0011a2634d4cce` |

## 출처 확인

tarball은 레지스트리 메타데이터(`https://registry.npmjs.org/<이름>/<버전>`)의 `dist.integrity`(sha512)와 일치하는 것만 썼다.

| tarball | dist.integrity |
|---|---|
| `htmx.org-2.0.11.tgz` | `sha512-Thx/WtpeOQqSrqBCw/A1cwGJGg4UrVa3+sW0GmrM3p4gJgO89ecH4qtbnyzDDWFvBTqjnIMCgELTNt636dtamA==` |
| `chart.js-4.5.1.tgz` | `sha512-GIjfiT9dbmHRiYi6Nl2yFCq7kkwdkp1W/lp2J99rX0yo9tgJGn3lKQATztIjb5tVtevcBtIdICNWqlq5+E8/Pw==` |

## 교체할 때

1. 새 버전의 tarball을 받아 `dist.integrity`를 확인하고, 압축은 `tarfile`의 `filter="data"`로 푼다.
2. 파일 이름의 버전, 이 표, `base.html`·`dashboard.html`의 `<script src>`를 함께 고친다.
3. `tests/web/test_static.py`가 이 표의 sha256과 실제 파일을 비교한다.

`chart-4.5.1.umd.min.js` 끝의 `sourceMappingURL` 주석은 원본 그대로다. 개발자 도구를 열었을 때만 `.map` 파일을 찾으며, 없어도 동작에는 영향이 없다.
