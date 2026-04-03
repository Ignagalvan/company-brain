/**
 * E2E tests: document persistence.
 *
 * Uses an in-memory fake PDF buffer — no text content,
 * so no embeddings are generated on the backend.
 */

import { test, expect, Page } from '@playwright/test'

const RUN_ID = Date.now()

// Minimal bytes that satisfy the .pdf filename check but have no extractable text
const FAKE_PDF_BUFFER = Buffer.from('%PDF-1.4 e2e-test-no-content')

async function uploadPdf(page: Page, filename: string) {
  await page.locator('[data-testid="file-input"]').setInputFiles({
    name: filename,
    mimeType: 'application/pdf',
    buffer: FAKE_PDF_BUFFER,
  })
  // Upload button becomes active once a file is selected
  await page.click('[data-testid="upload-btn"]')
}

async function waitForDocumentInSidebar(page: Page, nameFragment: string) {
  await expect(
    page.locator('[data-testid="document-item"]').filter({ hasText: nameFragment })
  ).toBeVisible()
}

// ─── Tests ────────────────────────────────────────────────────────────────────

test('subir PDF aparece en el sidebar', async ({ page }) => {
  const uid = `${RUN_ID}-upload`
  await page.goto('/app')

  await uploadPdf(page, `doc-${uid}.pdf`)
  await waitForDocumentInSidebar(page, `doc-${uid}.pdf`)
})

test('documento subido persiste al recargar', async ({ page }) => {
  const uid = `${RUN_ID}-persist`
  await page.goto('/app')

  await uploadPdf(page, `doc-${uid}.pdf`)
  await waitForDocumentInSidebar(page, `doc-${uid}.pdf`)

  // Reload and verify still present
  await page.reload()
  await waitForDocumentInSidebar(page, `doc-${uid}.pdf`)
})

test('borrar documento lo elimina del sidebar', async ({ page }) => {
  const uid = `${RUN_ID}-delete-ui`
  await page.goto('/app')

  await uploadPdf(page, `doc-${uid}.pdf`)
  const docItem = page.locator('[data-testid="document-item"]').filter({ hasText: `doc-${uid}.pdf` })
  await expect(docItem).toBeVisible()

  // Hover to reveal × button, then click
  await docItem.hover()
  const deleteBtn = docItem.locator('[data-testid="delete-doc-btn"]')
  await expect(deleteBtn).toBeVisible()
  await deleteBtn.click()

  await expect(docItem).not.toBeVisible()
})

test('documento borrado no vuelve al recargar', async ({ page }) => {
  const uid = `${RUN_ID}-delete-persist`
  await page.goto('/app')

  await uploadPdf(page, `doc-${uid}.pdf`)
  const docItem = page.locator('[data-testid="document-item"]').filter({ hasText: `doc-${uid}.pdf` })
  await expect(docItem).toBeVisible()

  // Delete
  await docItem.hover()
  const deleteBtn = docItem.locator('[data-testid="delete-doc-btn"]')
  await expect(deleteBtn).toBeVisible()
  await deleteBtn.click()
  await expect(docItem).not.toBeVisible()

  // Reload and verify still gone
  await page.reload()
  await expect(
    page.locator('[data-testid="document-item"]').filter({ hasText: `doc-${uid}.pdf` })
  ).not.toBeVisible()
})
