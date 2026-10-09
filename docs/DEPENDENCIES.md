# Dependencies and reproducibility

Direct versions are pinned in frontend/package.json and backend/requirements.in.
npm's lockfile pins the frontend graph. Production Python dependencies also have
SHA-256 hashes; the development lock pins the full test/tool graph without hashes.
C++ dependencies use immutable Git commits in instrument/CMakeLists.txt.
Runtime/toolchain base images are pinned by digest. Debian package security updates
are resolved during the C++ build; the entire apt repository is not snapshotted.

Upstream license declarations for principal dependencies:
- React, Vite, Recharts, FastAPI, nlohmann/json, doctest: MIT.
- Asio: Boost Software License 1.0.
- PostgreSQL: PostgreSQL License.
- Psycopg: LGPLv3; packaged binary components include their upstream notices.
- Python: Python Software Foundation License; GCC: GPL with runtime exceptions.
- TypeScript and Playwright: Apache-2.0; Uvicorn: BSD-3-Clause.

Upstream source/license references are available from each pinned package's metadata
and the C++ source repositories declared in CMake. Keep those notices when
redistributing third-party code or binaries. Project source licensing remains
undecided; no first-party LICENSE has been selected.

No third-party photographs, fonts, icons or purchased assets are included. The UI
uses system fonts, text symbols and real screenshots of synthetic runs.
