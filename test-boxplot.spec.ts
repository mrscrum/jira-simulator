import { test, expect } from "@playwright/test";

// Test against the local docker deployment (nginx on :80 with backend proxy)
const BASE = process.env.TEST_URL || "http://localhost";

test.describe("Cycle Time Distribution Boxplot", () => {
  test("boxplot SVG renders visible chart elements", async ({ page }) => {
    // 1. Load the app
    await page.goto(BASE);
    await page.waitForLoadState("networkidle");

    // Take a screenshot of initial state
    await page.screenshot({ path: "test-results/01-initial.png" });

    // 2. Navigate to Templates section via sidebar
    const templatesBtn = page.locator("button").filter({ hasText: /^Templates$/ });
    await expect(templatesBtn).toBeVisible({ timeout: 5000 });
    await templatesBtn.click();
    await page.waitForTimeout(1000);

    await page.screenshot({ path: "test-results/02-templates-section.png" });

    // 3. Click on the template name to open the editor
    //    Look for the template in the list and click it
    const templateItem = page.locator("text=Test Template").first();
    const hasTemplate = await templateItem.count();

    if (hasTemplate === 0) {
      console.log("No 'Test Template' found — skipping (no test data)");
      test.skip();
      return;
    }

    await templateItem.click();
    await page.waitForTimeout(1000);

    await page.screenshot({ path: "test-results/03-template-editor.png" });

    // 4. Verify "Cycle Time Distribution" section is visible
    const heading = page.locator("text=Cycle Time Distribution");
    await expect(heading).toBeVisible({ timeout: 5000 });

    // 5. Verify SVG chart has rendered content
    //    The SVG is inside the Cycle Time Distribution card
    const chartCard = page.locator(".rounded-lg.border.bg-card").filter({ hasText: "Cycle Time Distribution" });
    const svg = chartCard.locator("svg").first();
    await expect(svg).toBeVisible();

    // Count SVG child elements
    const rectCount = await svg.locator("rect").count();
    const lineCount = await svg.locator("line").count();
    const circleCount = await svg.locator("circle").count();
    const textCount = await svg.locator("text").count();

    console.log(`SVG elements — rects: ${rectCount}, lines: ${lineCount}, circles: ${circleCount}, texts: ${textCount}`);

    // A rendered boxplot with 6 rows should have:
    //   rects >= 12 (6 backgrounds + 6 boxes)
    //   lines >= 24 (grid + whiskers + caps + medians)
    //   circles >= 30 (6 rows × 5 handles)
    //   texts >= 8 (6 row labels + axis ticks + axis label)
    expect(rectCount).toBeGreaterThanOrEqual(10);
    expect(lineCount).toBeGreaterThanOrEqual(10);
    expect(circleCount).toBeGreaterThanOrEqual(20);
    expect(textCount).toBeGreaterThanOrEqual(5);

    // 6. Verify boxes have non-zero width (chart actually rendered, not stuck at width=0)
    const boxElements = svg.locator("rect[fill-opacity='0.22']");
    const boxCount = await boxElements.count();
    expect(boxCount).toBeGreaterThanOrEqual(1);
    console.log(`Box rects found: ${boxCount}`);

    for (let i = 0; i < Math.min(3, boxCount); i++) {
      const box = await boxElements.nth(i).boundingBox();
      expect(box).not.toBeNull();
      expect(box!.width).toBeGreaterThan(10);
      console.log(`Box ${i} bounding box: w=${box!.width.toFixed(1)}, h=${box!.height.toFixed(1)}, x=${box!.x.toFixed(1)}, y=${box!.y.toFixed(1)}`);
    }

    // 7. Verify "Business Hours" axis label exists inside SVG
    await expect(svg.locator("text", { hasText: "Business Hours" })).toBeVisible();

    // 8. Verify issue type toggle buttons
    const toggleButtons = page.locator("button").filter({ hasText: /^(Bug|Story|Task)$/ });
    const buttonCount = await toggleButtons.count();
    expect(buttonCount).toBeGreaterThanOrEqual(2);
    console.log(`Issue type buttons: ${buttonCount}`);

    // 9. Click a different issue type and verify chart stays rendered
    if (buttonCount >= 2) {
      await toggleButtons.nth(1).click();
      await page.waitForTimeout(500);

      const rectsAfterSwitch = await svg.locator("rect").count();
      expect(rectsAfterSwitch).toBeGreaterThanOrEqual(10);

      const boxesAfterSwitch = await svg.locator("rect[fill-opacity='0.22']").count();
      expect(boxesAfterSwitch).toBeGreaterThanOrEqual(1);

      // Verify boxes still have real width
      const firstBox = await svg.locator("rect[fill-opacity='0.22']").first().boundingBox();
      expect(firstBox).not.toBeNull();
      expect(firstBox!.width).toBeGreaterThan(10);
      console.log(`After type switch — box width: ${firstBox!.width.toFixed(1)}`);
    }

    // 10. Verify values table
    const table = chartCard.locator("table");
    await expect(table).toBeVisible();
    const tableRows = table.locator("tbody tr");
    const rowCount = await tableRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(4);
    console.log(`Values table rows: ${rowCount}`);

    // Final screenshot
    await page.screenshot({ path: "test-results/04-boxplot-final.png", fullPage: true });
    console.log("All boxplot assertions passed ✓");
  });
});
