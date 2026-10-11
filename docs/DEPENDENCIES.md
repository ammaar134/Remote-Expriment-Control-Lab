# Dependencies and reproducibility

Phase 4 adds no application dependency. The timestamp plot is original SVG; both
devices run the same pinned C++ build. Final verification runs npm audit and
pip-audit 2.10.1 against the pinned Python production lock, with full-history
Gitleaks in CI. These check known package advisories and secret patterns; they
are not a penetration test, container-OS vulnerability certification or proof of
the absence of defects. Existing test-library deprecation warnings do not affect
the production runtime. Exact release evidence is recorded in PROGRESS.md.

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

The UI self-hosts Manrope under the included SIL Open Font License notice in
`frontend/public/fonts/OFL-Manrope.txt`. Icons and the projected wireframe are
original SVG; screenshots show real synthetic runs. No third-party photographs or
purchased assets are included. The public 21st.dev page is a visual reference only,
as documented in DESIGN_BRIEF.md; no account-locked implementation was copied.
