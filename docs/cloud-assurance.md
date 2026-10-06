# Cloud Assurance: from evidence collection to control readiness

The Operations workspace answers “what was submitted, who reviewed it, and what was approved?” Cloud Assurance adds the next question: “which control objective does this evidence support, and what is still missing?” This is a current extension of the public engineering reference, using authored synthetic evidence. It is not employer work or a historical client engagement.

## Implemented workflow

1. Open the Cloud Assurance tab, or `/#cloud`.
2. Inspect eight common control objectives and their candidate domain links across ISO 27001, SOC 2, ISMS-P, CSAP and financial-sector CSP Safety.
3. Run bounded checks on four normalized AWS evidence types: root MFA, S3 bucket public-access blocks, CloudTrail settings and eligible KMS key rotation.
4. Distinguish ready-for-review, gap, missing, stale, invalid, out-of-scope and manual-review outcomes. The fixed sample's assessment date is explicit; freshness uses a **project-defined 90-day policy**, not an asserted regulatory deadline.
5. Inspect observed fields, expected values, source metadata, SHA-256 and the residual human review procedure. Hashes identify normalized submitted content; they do not authenticate the collector or prove cloud provenance.
6. Edit the synthetic bundle, rerun and export the complete JSON review pack. An edit invalidates the previous output until a successful rerun. Recommended owners and next actions are included; this is not a persistent ticketing system.

The stateless API does not store submissions or call AWS. The public editor is intended for synthetic data only. Raw request bodies are capped at 100 KB before parsing. The evidence schema is strict about keys and dates. Boolean strings cannot pass boolean rules. Account/region metadata must match the declared scope. Metadata is self-declared and requires reviewer verification. Only one supplied resource per control is assessed: no population completeness or account-wide coverage claim is made.

## Control crosswalk methodology

A common objective is an authored abstraction, not a claim that two standards are equivalent. Every edge is explicitly `candidate_domain_overlap`. Framework edition/scope notes and official entry-point links are retained in the versioned catalog. The links ground the source framework and technical checks; **they do not validate the authored crosswalk**. Exact clause IDs and licensed criteria are intentionally not reproduced or invented. A reviewer must obtain the applicable current criteria, select certification/service scope and verify each mapping before use in an audit.

**CSAP and CSP Safety are separate schemes.** KISA describes CSAP as cloud-service security certification, including services intended for public-sector use. FSEC publishes the financial-sector cloud-use guide and provides CSP safety assessment support. Passing one demonstration rule establishes neither certification nor equivalence between the schemes.

## Technical boundaries that matter

| Check | What it establishes | What it does not establish |
|---|---|---|
| IAM | Submitted integer root MFA flag matches 1 | Least privilege, all-user MFA, effective root-access governance |
| S3 | Four bucket-level public-access-block flags match the strict project baseline | Public exposure when a flag is false; account/organization protections may apply |
| CloudTrail | Submitted multi-region, integrity and logging flags match | Correct selectors, log delivery, retention or actual digest validation |
| KMS | Submitted automatic rotation flag matches for an eligible key | Every key supports automatic rotation; key policy or full lifecycle effectiveness |
| Incident, recovery, provider, location | Material is present for human review | Document presence is not an operating-effectiveness test |

CloudTrail input combines `describe-trails` and `get-trail-status`; IAM input extracts `SummaryMap` from `get-account-summary`. These are explicit normalization contracts. No live collector is implemented. No cloud spend or credentials are needed.

## Reproduce

```bash
python -m pytest tests/test_cloud_assurance.py -q
python -m pytest -q
cd frontend
npm ci && npm run build
npx playwright test tests/cloud-assurance.spec.ts
```

Endpoints: `GET /api/cloud-assurance/catalog`, `GET /api/cloud-assurance/sample`, `POST /api/cloud-assurance/assess`. The original Operations endpoints and database model are unchanged. The module is additive and can be removed without a data migration. The earlier desktop/LangGraph branch remains a separate unmerged change.

## Primary references

- [AWS IAM account summary](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetAccountSummary.html)
- [AWS S3 public-access blocks](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)
- [CloudTrail trail settings](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_Trail.html)
- [CloudTrail status](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_GetTrailStatus.html)
- [KMS key rotation status](https://docs.aws.amazon.com/kms/latest/APIReference/API_GetKeyRotationStatus.html)
- [AWS shared responsibility](https://aws.amazon.com/compliance/shared-responsibility-model/)
- [ISO 27001](https://www.iso.org/standard/27001)
- [AICPA Trust Services Criteria](https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022)
- [KISA ISMS-P](https://isms.kisa.or.kr/)
- [KISA CSAP](https://www.kisa.kr/1050603)
- [FSEC financial cloud-use guide, 2025 revision](https://www.fsec.or.kr/bbs/detail?bbsNo=11691&menuNo=222)

Catalog version: `2026-10-06.1`. Framework mapping maturity: authored domain-level study; no auditor validation or complete certification coverage.
