# Adjacent Repos

CAPS is the shell. Product and workflow repos own their own substance.

Use this contract when the public kit needs to point at a specific product,
course, cohort, or workflow library without becoming that repo.

## Relationship Model

| Repo | Owns | Does Not Own |
| --- | --- | --- |
| `caps-productivity-kit` | Generic CAPS install shell, conductor and worker prompts, proof contracts, naming conventions, public-safe templates, sanitized examples | Paid course access, private launch proof, product runtime, private member/customer data |
| `Full Circle` | FC5 student OS, tier packs, gated links, lesson bodies, cohort operations | Generic CAPS shell patterns that should be reusable outside Full Circle |
| `Threadify-Workflows` | Reusable creator-growth recipes, workflow templates, dry-run review patterns | Live Threadify app runtime, private Full Circle content, production account state |

## Public Link Rules

Only link an adjacent repo when the link target is approved for the audience.

Do not put these in CAPS:

- Premium, VIP, or paid lesson bodies.
- Private proof paths, screenshots, member data, or launch gates.
- Internal business details.
- Live app runtime secrets or production account details.
- Private thread IDs.

## Template Candidates

Public-safe prompt templates can live in CAPS when they are generic:

- Adjacent repo router prompt.
- Pack manifest template.
- Daily review lane prompt.
- Proof contract template.
- Approval-gate checklist.

Product-specific templates should live in the owning repo:

- FC5 tier-specific packs.
- FC5 lesson bodies.
- Threadify workflow recipes with product-specific scoring or examples.
- Any template that depends on private product data.

## Runtime Limits

CAPS can install prompts, templates, checklists, and links. It cannot guarantee
automatic app-level thread creation, pinning, renaming, publishing, scheduling,
or production writes unless the active runtime exposes safe tools and the user
has approved that action.
