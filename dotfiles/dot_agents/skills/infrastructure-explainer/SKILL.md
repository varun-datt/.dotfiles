---
name: infrastructure-explainer
description: "Manual-only. Explain infrastructure code to people who do not know it; a reader exists for Terraform, and readers for Kubernetes, Helm and networking are written from their first real run. Read the code and every module it pins, work out what each account and environment gets and who else can reach it, check each claim against code or read-only live calls, then draw it with the official AWS icons in one self-contained HTML page and explain it in plain words with numbered steps and a short guide to each AWS service. Use only when the owner invokes it."
argument-hint: "<path to the infrastructure repo, and who the explanation is for>"
disable-model-invocation: true
---

# Infrastructure explainer

Turns infrastructure code into a picture and a plain explanation that a newcomer can follow: what gets created, how the pieces connect, who else can reach them, and what differs between accounts. The method is reading and checking; the drawing comes last and shows only what was checked.

## Readers

The steps and the drawing kit are the same for every source; reading is not. Each reader is written from a real run, not ahead of one.

| Source | Reader |
| ------ | ------ |
| Terraform | [references/reading-terraform.md](references/reading-terraform.md) |
| Kubernetes and Helm | not written yet |
| Networking | not written yet |

For a source without a reader, answer the same questions (what each account and environment gets, who else can reach it, what differs), then write its reader from that run.

## Tools that already exist

Use one of these instead when it answers the question; this skill is for when none does.

| Tool | Reads | Gives | Limits |
| ---- | ----- | ----- | ------ |
| `terraform graph` | one root module | its dependency graph (DOT) | no icons, no per-account view, no explanation |
| [InfraMap](https://github.com/cycloidio/inframap) | tfstate or HCL | a graph of the main resources per provider (DOT) | no per-account view, no access grants, no explanation |
| [AWS diagram-as-code](https://github.com/awslabs/diagram-as-code) | a YAML file you write (CloudFormation in beta) | an AWS diagram with official icons | does not read Terraform; you still do the analysis |
| [Diagrams](https://github.com/mingrammer/diagrams) | Python you write | a diagram with provider icons, laid out by Graphviz | does not read Terraform; automatic layout |

None of them works out who else can reach a resource, what one account gets that another does not, or what a newcomer needs explained. Those come from reading, which is most of this skill.

## Steps

1. **Agree the scope before reading.** Ask who the picture is for, which accounts and environments it covers, and the one question it must answer. Do not guess the audience or the chart type.
2. **Take an inventory** of what is created, per account and per environment, by following the source's reader ([Readers](#readers)). Write each fact with its source (file and line, or command) as you go.
3. **Check what you will draw.** Code shows what is declared; read-only live calls (`aws ... list/get/describe`) show what exists. Mark each fact VERIFIED, INFERRED or OPEN. A mechanism that is not verified stays off the picture and goes in the notes.
4. **Get the icons.** Download the asset package from https://aws.amazon.com/architecture/icons/ (AWS: "We allow customers and partners to use these toolkits and assets to create architecture diagrams"). Keep it out of public repositories. Find and copy icons with `scripts/aws_icons.py`.
5. **Draw** with a short build script that imports `scripts/diagram_kit.py`; panel patterns and layout tips are in [references/drawing.md](references/drawing.md). `scripts/example_build.py` is a working example.
6. **Explain in plain words** under each panel: numbered steps that match the numbers on the arrows, the real names of the outside parties (an IAM role, a Lambda, an event bus, not "the analytics team"), and a short guide to each AWS service in the picture.
7. **Render and look.** `scripts/render_cards.py page.html out/` saves the full page and each panel as a PNG. Open every crop: clipped text, overlaps and stray arrows only show in the render.
8. **Split lasting from passing.** What the repo creates is lasting reference. A plan ("today against after the change") or an options comparison is a proposal page that expires once decided. Ask where each one lives.

## Traps

- **Names are not stable.** Many shared modules add a random suffix to the physical name, so a resource that is re-created comes back with a new name, and every consumer that hard-codes it breaks. Find the consumers before saying "re-create is fine".
- **A grant is not a use.** A bucket policy that names another account's role says that role may read; the other side's code or the access logs say whether it does.
- **An empty search can be a wrong path.** Repositories differ (`charts/` against `helm-charts/`); confirm a zero with a second, different search before writing "none".
- **Keep account numbers out of the picture and the page.** Role, bucket and bus names are usually fine; ask when unsure.
- **Expired credentials can look like "nothing there".** Assert a non-empty control result before believing an empty list.
