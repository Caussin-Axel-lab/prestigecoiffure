# Head spa Hero B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the head spa service hero with Canon frame B while preserving the site's warm cinematic direction and responsive behavior.

**Architecture:** Develop the selected Canon frame with the existing ambient-only workflow, then feed the resulting master through the existing derivative builder. Update only the head spa service hero references and verify all photo contracts.

**Tech Stack:** Static HTML, Pillow/raw Canon export, WebP/JPEG derivative pipeline, Python unittest suite.

---

### Task 1: Prepare the selected Canon frame

**Files:**
- Modify: `photosalon/service-head-spa.jpg`
- Modify: `photosalon/retouched/service-head-spa.png`
- Modify: `photosalon/web/service-head-spa-desktop.*`
- Modify: `photosalon/web/service-head-spa-mobile.*`
- Modify: `scripts/photo-master-hashes.json`

- [x] **Step 1: Export frame B from `IMG_4828.CR3` with the already approved ambient grade and native dimensions.**
- [x] **Step 2: Regenerate the service master and its desktop/mobile derivatives.**
- [x] **Step 3: Verify output dimensions, metadata, and deterministic hashes.**

### Task 2: Integrate and validate the service hero

**Files:**
- Modify: `services/head-spa.html:200-205`
- Test: `scripts/test_*.py`

- [x] **Step 1: Point the head spa `<picture>` sources to the refreshed service derivatives and update the alt text to describe the immersive basin-and-steam view.**
- [x] **Step 2: Run `python scripts/verify-photo-assets.py` and `python scripts/build-photo-derivatives.py --verify`.**
- [x] **Step 3: Run `python -B -m unittest discover -s scripts -p 'test_*.py'`.**
- [x] **Step 4: Inspect the hero in light and dark mode at the existing local preview.**
- [x] **Step 5: Commit with `git commit -m "feat: use immersive head spa hero"`.**
