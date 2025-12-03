# ASCII Diagram Tools Comparison

This document compares ASCII diagramming tools for architectural and workflow diagrams.

## Summary

| Tool | Best For | Alignment | Versatility | Complexity | Verdict |
|------|----------|-----------|-------------|------------|---------|
| **graph-easy** | Architecture & Workflows | Perfect | High | Simple DSL | **RECOMMENDED** |
| **boxes** | Component Labels | Perfect | Medium | Simple | Good for titles |
| **ditaa** | PNG Export | N/A | High | Medium | Image output only |
| **pyfiglet** | Text Banners | Perfect | Low | Simple | Headers only |
| **asciidraw** | Coloring | N/A | Low | N/A | Not useful |

## Winner: Graph::Easy

**Installation**: `apt-get install libgraph-easy-perl`

**Why it's the best**:
1. Automatic box alignment (no manual spacing)
2. Handles complex multi-path flows
3. Labeled edges for relationship descriptions
4. Both ASCII and Unicode (boxart) output
5. Simple declarative syntax

---

## Graph::Easy Examples

### Basic Flow
```bash
cat > /tmp/flow.txt << 'EOF'
[Doppler] -> [GitHub Secrets] -> [GitHub Actions]
EOF
graph-easy /tmp/flow.txt --as_ascii
```

Output:
```
+---------+     +----------------+     +----------------+
| Doppler | --> | GitHub Secrets | --> | GitHub Actions |
+---------+     +----------------+     +----------------+
```

### Multi-Path with Labels
```bash
cat > /tmp/multipath.txt << 'EOF'
[Doppler] -- auto-sync --> [GitHub Secrets]
[Doppler] -- service token --> [Local Access]
[GitHub Secrets] -- env vars --> [Workflow]
EOF
graph-easy /tmp/multipath.txt --as_ascii
```

Output:
```
+----------------+  auto-sync   +----------------+  env vars   +----------+
|    Doppler     | -----------> | GitHub Secrets | ----------> | Workflow |
+----------------+              +----------------+             +----------+
  |
  | service token
  v
+----------------+
|  Local Access  |
+----------------+
```

### CI/CD Workflow
```bash
cat > /tmp/cicd.txt << 'EOF'
graph { flow: east; }
[Trigger] -> [Checkout] -> [Secrets] -> [Test] -> [Deploy] -> [Notify]
[Test] -- on failure --> [Alert]
[Deploy] -- on success --> [Release]
EOF
graph-easy /tmp/cicd.txt --as_boxart
```

Output:
```
┌─────────┐     ┌──────────┐     ┌─────────┐     ┌──────┐     ┌────────┐     ┌────────┐
│ Trigger │ ──> │ Checkout │ ──> │ Secrets │ ──> │ Test │ ──> │ Deploy │ ──> │ Notify │
└─────────┘     └──────────┘     └─────────┘     └──────┘     └────────┘     └────────┘
                                                   │            │
                                                   │ on failure │ on success
                                                   ∨            ∨
                                                 ┌──────┐     ┌─────────┐
                                                 │ Alert│     │ Release │
                                                 └──────┘     └─────────┘
```

### Complex Hierarchy
```bash
cat > /tmp/hierarchy.txt << 'EOF'
graph { flow: south; }

[GitHub Account] -> [Personal Repos]
[GitHub Account] -> [Organization]

[Organization] -> [Org Secrets]
[Organization] -> [Org Repos]

[Org Secrets] -- shared --> [Org Repos]

[Personal Repos] -> [Repo Secrets]
[Org Repos] -> [Repo Secrets 2]

[Repo Secrets] { label: ISOLATED\nPer-repo only }
[Repo Secrets 2] { label: ISOLATED + Org\nPer-repo + shared }
EOF
graph-easy /tmp/hierarchy.txt --as_boxart
```

Output:
```
┌────────────────┐     ┌───────────────────┐
│ Personal Repos │ <── │  GitHub Account   │
└────────────────┘     └───────────────────┘
  │                      │
  │                      │
  ∨                      ∨
┌────────────────┐     ┌───────────────────┐
│    ISOLATED    │     │   Organization    │
│ Per-repo only  │     │                   │ ─┐
└────────────────┘     └───────────────────┘  │
                         │                    │
                         ∨                    │
                       ┌───────────────────┐  │
                       │    Org Secrets    │  │
                       └───────────────────┘  │
                         │                    │
                         │ shared             │
                         ∨                    │
                       ┌───────────────────┐  │
                       │     Org Repos     │ <┘
                       └───────────────────┘
                         │
                         ∨
                       ┌───────────────────┐
                       │  ISOLATED + Org   │
                       │ Per-repo + shared │
                       └───────────────────┘
```

---

## Graph::Easy Syntax Reference

### Nodes
```
[Simple Node]
[Node] { label: Custom\nMulti-line }
```

### Edges
```
[A] -> [B]                    # Arrow
[A] -- label --> [B]          # Labeled arrow
[A] <- [B]                    # Reverse arrow
[A] <-> [B]                   # Bidirectional
[A] - [B]                     # No arrow (line)
```

### Layout Direction
```
graph { flow: east; }         # Left to right (default)
graph { flow: south; }        # Top to bottom
graph { flow: west; }         # Right to left
graph { flow: north; }        # Bottom to top
```

### Output Formats
```bash
graph-easy input.txt --as_ascii    # ASCII art (default)
graph-easy input.txt --as_boxart   # Unicode boxes (prettier)
graph-easy input.txt --as_svg      # SVG vector
graph-easy input.txt --as_dot      # Graphviz DOT format
```

---

## Boxes Examples

**Installation**: `apt-get install boxes`

Best for: Simple component labels, not flowcharts.

```bash
echo "GitHub Secrets" | boxes -d stone
```
```
+----------------+
| GitHub Secrets |
+----------------+
```

```bash
echo -e "DOPPLER\nSecretOps" | boxes -d simple
```
```
*************
* DOPPLER   *
* SecretOps *
*************
```

### Useful Box Styles
- `stone` - Clean rectangle
- `simple` - Asterisk border
- `columns` - Decorative pillars
- `ian_jones` - Double-line border

---

## PyFiglet Examples

**Installation**: `pip install pyfiglet`

Best for: Large text banners/headers.

```python
from pyfiglet import Figlet
f = Figlet(font='small')
print(f.renderText('ARCH'))
```
```
   _   ___  ___ _  _
  /_\ | _ \/ __| || |
 / _ \|   / (__| __ |
/_/ \_\_|_\\___|_||_|
```

---

## Ditaa (Not Recommended for ASCII)

**Installation**: `apt-get install ditaa`

Ditaa converts ASCII to PNG images - not useful for pure ASCII output.
Better alternatives: Graph::Easy for ASCII, or Mermaid/PlantUML for images.

---

## Recommendation Matrix

| Use Case | Recommended Tool |
|----------|-----------------|
| Architecture diagrams | `graph-easy --as_boxart` |
| Workflow/pipeline flows | `graph-easy --as_boxart` |
| Secrets/data flow | `graph-easy --as_ascii` |
| Component labels | `boxes -d stone` |
| Section headers | `pyfiglet` |
| README diagrams | `graph-easy` (copy output) |
| SVG/image export | `graph-easy --as_svg` |

---

## Quick Reference

```bash
# Install recommended tools
apt-get install libgraph-easy-perl boxes
pip install pyfiglet

# Create architecture diagram
echo '[A] -> [B] -> [C]' > /tmp/d.txt && graph-easy /tmp/d.txt --as_boxart

# Create labeled box
echo "Component Name" | boxes -d stone

# Create banner
python3 -c "from pyfiglet import Figlet; print(Figlet(font='small').renderText('TITLE'))"
```
