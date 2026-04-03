/**
 * E2E tests: conversation persistence.
 *
 * Prerequisites (both must be running):
 *   - Frontend: http://localhost:3000
 *   - Backend:  http://localhost:8000  (OPENAI_API_KEY can be empty)
 *
 * When OPENAI_API_KEY is empty, the backend returns a fallback answer
 * without calling OpenAI. Persistence (DB) is still real.
 */

import { test, expect, Page } from '@playwright/test'

// Each test run uses a unique suffix to avoid collisions across runs
const RUN_ID = Date.now()

async function sendMessage(page: Page, content: string) {
  await page.fill('[data-testid="message-input"]', content)
  await page.click('[data-testid="send-btn"]')
}

async function waitForConversationInSidebar(page: Page, textFragment: string) {
  await expect(
    page.locator('[data-testid="conversation-item"]').filter({ hasText: textFragment })
  ).toBeVisible()
}

// ─── Tests ────────────────────────────────────────────────────────────────────

test('crear conversación aparece en el sidebar', async ({ page }) => {
  const uid = `${RUN_ID}-create`
  await page.goto('/app')

  await sendMessage(page, `Pregunta E2E ${uid}`)
  await waitForConversationInSidebar(page, uid)
})

test('conversación persiste al recargar', async ({ page }) => {
  const uid = `${RUN_ID}-persist`
  await page.goto('/app')

  await sendMessage(page, `Pregunta E2E ${uid}`)
  await waitForConversationInSidebar(page, uid)

  // Reload and verify still present
  await page.reload()
  await waitForConversationInSidebar(page, uid)
})

test('borrar conversación la elimina del sidebar', async ({ page }) => {
  const uid = `${RUN_ID}-delete-ui`
  await page.goto('/app')

  await sendMessage(page, `Pregunta E2E ${uid}`)
  const convItem = page.locator('[data-testid="conversation-item"]').filter({ hasText: uid })
  await expect(convItem).toBeVisible()

  // Hover to reveal × button, then click
  await convItem.hover()
  const deleteBtn = convItem.locator('[data-testid="delete-conversation-btn"]')
  await expect(deleteBtn).toBeVisible()
  await deleteBtn.click()

  // Verify it's gone immediately
  await expect(convItem).not.toBeVisible()
})

test('conversación borrada no vuelve al recargar', async ({ page }) => {
  const uid = `${RUN_ID}-delete-persist`
  await page.goto('/app')

  await sendMessage(page, `Pregunta E2E ${uid}`)
  const convItem = page.locator('[data-testid="conversation-item"]').filter({ hasText: uid })
  await expect(convItem).toBeVisible()

  // Delete
  await convItem.hover()
  const deleteBtn = convItem.locator('[data-testid="delete-conversation-btn"]')
  await expect(deleteBtn).toBeVisible()
  await deleteBtn.click()
  await expect(convItem).not.toBeVisible()

  // Reload and verify still gone
  await page.reload()
  await expect(
    page.locator('[data-testid="conversation-item"]').filter({ hasText: uid })
  ).not.toBeVisible()
})
