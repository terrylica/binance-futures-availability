# Secrets Management Architecture

## 1. GitHub Secrets Scope Hierarchy

```
+===========================================================================+
||                          GITHUB ACCOUNT                                  ||
||                         (terrylica)                                      ||
+===========================================================================+
|                                                                           |
|  +---------------------------------------------------------------------+  |
|  |                    ORGANIZATION LEVEL (if applicable)               |  |
|  |                    github.com/orgs/eonlabs                          |  |
|  +---------------------------------------------------------------------+  |
|  |                                                                     |  |
|  |   +-------------------+                                             |  |
|  |   | Org Secrets       |                                             |  |
|  |   +-------------------+                                             |  |
|  |   | SHARED_TOKEN_1    |----+                                        |  |
|  |   | SHARED_TOKEN_2    |----|---> Available to selected repos        |  |
|  |   +-------------------+    |     (configurable)                     |  |
|  |                            |                                        |  |
|  +----------------------------|----------------------------------------+  |
|                               |                                           |
|                               v                                           |
|  +------------------------+  +------------------------+  +-------------+  |
|  | REPOSITORY A          |  | REPOSITORY B           |  | REPOSITORY C |  |
|  | (binance-futures-     |  | (another-project)      |  | (...)        |  |
|  |  availability)        |  |                        |  |              |  |
|  +------------------------+  +------------------------+  +--------------+ |
|  |                        |  |                        |  |              |  |
|  | Repo-Level Secrets:    |  | Repo-Level Secrets:    |  | Repo-Level:  |  |
|  | +--------------------+ |  | +--------------------+ |  | +---------+  |  |
|  | | PUSHOVER_APP_TOKEN | |  | | DB_PASSWORD        | |  | | API_KEY |  |  |
|  | | PUSHOVER_USER_KEY  | |  | | API_SECRET         | |  | +---------+  |  |
|  | | DOPPLER_TOKEN      | |  | +--------------------+ |  |              |  |
|  | +--------------------+ |  |                        |  |              |  |
|  |                        |  |                        |  |              |  |
|  | +-ISOLATED-----------+ |  | +-ISOLATED-----------+ |  | +-ISOLATED-+ |  |
|  | | Cannot see B or C  | |  | | Cannot see A or C  | |  | | Can't    | |  |
|  | | secrets            | |  | | secrets            | |  | | see A/B  | |  |
|  | +--------------------+ |  | +--------------------+ |  | +----------+ |  |
|  +------------------------+  +------------------------+  +--------------+ |
|                                                                           |
+---------------------------------------------------------------------------+
```

## 2. Current Doppler Integration Flow

```
+---------------------------+
|       DOPPLER             |
|   (SecretOps Platform)    |
+---------------------------+
|                           |
| Project: notifications    |
| Config:  prd              |
|                           |
| +----------------------+  |
| | Secrets:             |  |
| | - PUSHOVER_APP_TOKEN |  |
| | - PUSHOVER_USER_KEY  |  |
| | - GH_TOKEN_*         |  |
| +----------------------+  |
|                           |
+------------+--------------+
             |
             | GitHub App Auto-Sync
             | (configured per-repo)
             |
             v
+---------------------------+       +---------------------------+
| GitHub Repository         |       | Other Repos               |
| binance-futures-          |       | (NOT synced unless        |
| availability              |       |  explicitly configured)   |
+---------------------------+       +---------------------------+
|                           |       |                           |
| Repository Secrets:       |       | No Doppler secrets here   |
| +----------------------+  |       | unless you add the repo   |
| | PUSHOVER_APP_TOKEN   |<-+       | to Doppler sync config    |
| | PUSHOVER_USER_KEY    |  |       |                           |
| | (auto-synced)        |  |       +---------------------------+
| +----------------------+  |
|                           |
| DOPPLER_TOKEN:            |
| +----------------------+  |
| | Manually added to    |  |
| | enable Doppler fetch |  |
| +----------------------+  |
|                           |
+------------+--------------+
             |
             | Used by
             v
+---------------------------+
| GitHub Actions Workflow   |
| .github/workflows/        |
| update-database.yml       |
+---------------------------+
|                           |
| steps:                    |
|   - uses: doppler-labs/   |
|     secrets-fetch-action  |
|     with:                 |
|       doppler-token:      |
|         ${{ secrets.      |
|         DOPPLER_TOKEN }}  |
|                           |
|   - name: Send Pushover   |
|     env:                  |
|       PUSHOVER_APP_TOKEN: |
|         ${{ secrets...}}  |
|                           |
+---------------------------+
```

## 3. Secret Visibility Matrix

```
+==================+==============+==============+==============+=============+
|                  | Repo A       | Repo B       | Repo C       | Forks of A  |
|                  | (this repo)  | (other)      | (other)      |             |
+==================+==============+==============+==============+=============+
| Repo A Secrets   |      ✓       |      ✗       |      ✗       |      ✗      |
| (PUSHOVER_*)     |   VISIBLE    |   BLOCKED    |   BLOCKED    |   BLOCKED   |
+------------------+--------------+--------------+--------------+-------------+
| Repo B Secrets   |      ✗       |      ✓       |      ✗       |      ✗      |
| (DB_PASSWORD)    |   BLOCKED    |   VISIBLE    |   BLOCKED    |   BLOCKED   |
+------------------+--------------+--------------+--------------+-------------+
| Org Secrets      |   DEPENDS    |   DEPENDS    |   DEPENDS    |      ✗      |
| (if configured)  |  on config   |  on config   |  on config   |   BLOCKED   |
+------------------+--------------+--------------+--------------+-------------+
| Workflow Logs    |   MASKED     |   MASKED     |   MASKED     |   N/A       |
| (all repos)      |   (****)     |   (****)     |   (****)     |             |
+==================+==============+==============+==============+=============+
```

## 4. Local Development vs CI/CD

```
+===========================================================================+
|                         DEVELOPMENT ENVIRONMENT                           |
+===========================================================================+
|                                                                           |
|   LOCAL MACHINE                          CI/CD (GitHub Actions)           |
|   +---------------------------+          +---------------------------+    |
|   |                           |          |                           |    |
|   |  Option A: .env.local     |          |  GitHub Secrets           |    |
|   |  +---------------------+  |          |  +---------------------+  |    |
|   |  | PUSHOVER_APP_TOKEN= |  |          |  | PUSHOVER_APP_TOKEN  |  |    |
|   |  | PUSHOVER_USER_KEY=  |  |          |  | PUSHOVER_USER_KEY   |  |    |
|   |  +---------------------+  |          |  +---------------------+  |    |
|   |  (in .gitignore)         |          |        |                   |    |
|   |                           |          |        v                   |    |
|   |  Option B: Doppler CLI    |          |  +---------------------+  |    |
|   |  +---------------------+  |          |  | Workflow YAML       |  |    |
|   |  | export DOPPLER_TOKEN|  |          |  | env:                |  |    |
|   |  | doppler run -- cmd  |  |          |  |   TOKEN: ${{        |  |    |
|   |  +---------------------+  |          |  |   secrets.TOKEN }}  |  |    |
|   |                           |          |  +---------------------+  |    |
|   +---------------------------+          +---------------------------+    |
|                                                                           |
|   SECURITY NOTES:                                                         |
|   +-------------------------------------------------------------------+   |
|   | - .env.local: chmod 600 (owner read/write only)                   |   |
|   | - Never commit .env files with real secrets                       |   |
|   | - Use .env.example as template (commit this)                      |   |
|   | - Doppler CLI fetches secrets at runtime (more secure)            |   |
|   +-------------------------------------------------------------------+   |
|                                                                           |
+===========================================================================+
```

## 5. Recommended Simple Architecture

```
+===========================================================================+
|                    SIMPLE SECURE ARCHITECTURE                             |
|                    (GitHub Secrets Only)                                  |
+===========================================================================+
|                                                                           |
|  +-----------------------------+      +-----------------------------+     |
|  |     LOCAL DEVELOPMENT       |      |     CI/CD (GitHub)          |     |
|  +-----------------------------+      +-----------------------------+     |
|  |                             |      |                             |     |
|  |  .env.local                 |      |  Repository Secrets         |     |
|  |  +------------------------+ |      |  +------------------------+ |     |
|  |  | PUSHOVER_APP_TOKEN=xxx | |      |  | PUSHOVER_APP_TOKEN     | |     |
|  |  | PUSHOVER_USER_KEY=yyy  | |      |  | PUSHOVER_USER_KEY      | |     |
|  |  +------------------------+ |      |  +------------------------+ |     |
|  |           |                 |      |           |                 |     |
|  |           v                 |      |           v                 |     |
|  |  +------------------------+ |      |  +------------------------+ |     |
|  |  | Python Script          | |      |  | GitHub Actions         | |     |
|  |  | load_dotenv()          | |      |  | ${{ secrets.* }}       | |     |
|  |  | os.getenv('TOKEN')     | |      |  +------------------------+ |     |
|  |  +------------------------+ |      |                             |     |
|  |                             |      |                             |     |
|  +-----------------------------+      +-----------------------------+     |
|                                                                           |
|  SETUP STEPS:                                                             |
|  +---------------------------------------------------------------------+  |
|  |                                                                     |  |
|  |  1. Create .env.example (commit this):                              |  |
|  |     +---------------------------+                                   |  |
|  |     | PUSHOVER_APP_TOKEN=       |                                   |  |
|  |     | PUSHOVER_USER_KEY=        |                                   |  |
|  |     +---------------------------+                                   |  |
|  |                                                                     |  |
|  |  2. Create .env.local (DO NOT commit):                              |  |
|  |     +---------------------------+                                   |  |
|  |     | PUSHOVER_APP_TOKEN=abc123 |                                   |  |
|  |     | PUSHOVER_USER_KEY=xyz789  |                                   |  |
|  |     +---------------------------+                                   |  |
|  |                                                                     |  |
|  |  3. Add to .gitignore:                                              |  |
|  |     +---------------------------+                                   |  |
|  |     | .env.local                |                                   |  |
|  |     | .env                      |                                   |  |
|  |     | *.env                     |                                   |  |
|  |     +---------------------------+                                   |  |
|  |                                                                     |  |
|  |  4. Set GitHub Secrets via UI:                                      |  |
|  |     Settings -> Secrets -> Actions -> New repository secret         |  |
|  |                                                                     |  |
|  +---------------------------------------------------------------------+  |
|                                                                           |
+===========================================================================+
```

## 6. Doppler vs GitHub Secrets Comparison

```
+===========================================================================+
|                      ARCHITECTURE COMPARISON                              |
+===========================================================================+
|                                                                           |
|  OPTION A: Doppler (Current)           OPTION B: GitHub Only (Simpler)    |
|  +--------------------------+          +--------------------------+       |
|  |                          |          |                          |       |
|  |  +------------------+    |          |  +------------------+    |       |
|  |  | Doppler Cloud    |    |          |  | GitHub Secrets   |    |       |
|  |  | (notifications/  |    |          |  | (per repository) |    |       |
|  |  |  prd)            |    |          |  +------------------+    |       |
|  |  +--------+---------+    |          |           |              |       |
|  |           |              |          |           |              |       |
|  |           | Sync         |          |           | Direct       |       |
|  |           v              |          |           v              |       |
|  |  +------------------+    |          |  +------------------+    |       |
|  |  | GitHub Secrets   |    |          |  | Workflow YAML    |    |       |
|  |  +--------+---------+    |          |  | ${{ secrets.* }} |    |       |
|  |           |              |          |  +------------------+    |       |
|  |           v              |          |                          |       |
|  |  +------------------+    |          |  PROS:                   |       |
|  |  | Workflow         |    |          |  + Zero external deps    |       |
|  |  +------------------+    |          |  + Free                  |       |
|  |                          |          |  + Simple                |       |
|  |  PROS:                   |          |                          |       |
|  |  + Audit trail           |          |  CONS:                   |       |
|  |  + Version control       |          |  - No versioning         |       |
|  |  + Multi-repo sync       |          |  - No audit trail        |       |
|  |  + Env separation        |          |  - Manual per-repo setup |       |
|  |                          |          |                          |       |
|  |  CONS:                   |          +--------------------------+       |
|  |  - Extra complexity      |                                             |
|  |  - Service dependency    |                                             |
|  +--------------------------+                                             |
|                                                                           |
+===========================================================================+
```

## 7. Security Threat Model

```
+===========================================================================+
|                         THREAT MODEL                                      |
+===========================================================================+
|                                                                           |
|  ATTACK VECTOR              MITIGATION                      STATUS        |
|  +----------------------+   +------------------------+   +-------------+  |
|  |                      |   |                        |   |             |  |
|  | Secret in Git        |-->| .gitignore + scanning  |-->| MITIGATED   |  |
|  | history              |   | + pre-commit hooks     |   |             |  |
|  +----------------------+   +------------------------+   +-------------+  |
|                                                                           |
|  +----------------------+   +------------------------+   +-------------+  |
|  |                      |   |                        |   |             |  |
|  | Log exposure         |-->| GitHub auto-masks      |-->| MITIGATED   |  |
|  |                      |   | secrets in logs        |   |             |  |
|  +----------------------+   +------------------------+   +-------------+  |
|                                                                           |
|  +----------------------+   +------------------------+   +-------------+  |
|  |                      |   |                        |   |             |  |
|  | Fork access          |-->| GitHub blocks secret   |-->| MITIGATED   |  |
|  |                      |   | access from forks      |   |             |  |
|  +----------------------+   +------------------------+   +-------------+  |
|                                                                           |
|  +----------------------+   +------------------------+   +-------------+  |
|  |                      |   |                        |   |             |  |
|  | Collaborator reads   |-->| Secrets are write-only |-->| MITIGATED   |  |
|  | secret values        |   | (can use, can't view)  |   |             |  |
|  +----------------------+   +------------------------+   +-------------+  |
|                                                                           |
|  +----------------------+   +------------------------+   +-------------+  |
|  |                      |   |                        |   |             |  |
|  | Local .env readable  |-->| chmod 600 .env.local   |-->| ACTION      |  |
|  | by other users       |   |                        |   | REQUIRED    |  |
|  +----------------------+   +------------------------+   +-------------+  |
|                                                                           |
|  +----------------------+   +------------------------+   +-------------+  |
|  |                      |   |                        |   |             |  |
|  | Token never rotated  |-->| Quarterly rotation     |-->| RECOMMENDED |  |
|  |                      |   | schedule               |   |             |  |
|  +----------------------+   +------------------------+   +-------------+  |
|                                                                           |
+===========================================================================+
```

## 8. Decision Matrix

```
+===========================================================================+
|                    WHICH APPROACH TO USE?                                 |
+===========================================================================+
|                                                                           |
|                            START                                          |
|                              |                                            |
|                              v                                            |
|                   +--------------------+                                  |
|                   | Need secrets in    |                                  |
|                   | multiple repos?    |                                  |
|                   +--------------------+                                  |
|                     |              |                                      |
|                    YES            NO                                      |
|                     |              |                                      |
|                     v              v                                      |
|           +----------------+  +------------------+                        |
|           | Need audit     |  | GitHub Secrets   |                        |
|           | trail?         |  | (per-repo)       |                        |
|           +----------------+  | RECOMMENDED      |                        |
|             |          |      +------------------+                        |
|            YES        NO                                                  |
|             |          |                                                  |
|             v          v                                                  |
|    +-------------+  +------------------+                                  |
|    | Doppler or  |  | Organization     |                                  |
|    | HashiCorp   |  | Secrets          |                                  |
|    | Vault       |  | (GitHub)         |                                  |
|    +-------------+  +------------------+                                  |
|                                                                           |
+===========================================================================+
```
