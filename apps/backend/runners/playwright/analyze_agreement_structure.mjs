#!/usr/bin/env node
/**
 * 深度分析协议区域的 DOM 结构
 */
import { chromium } from "playwright";

async function analyzeAgreementStructure() {
  const browser = await chromium.launch({ headless: false, slowMo: 1000 });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  try {
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    console.log("="*80);
    console.log("🔍 协议区域 DOM 结构深度分析");
    console.log("="*80);

    // 获取完整的协议区域 HTML
    const structure = await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      if (!policy) return { error: '未找到 .policy 元素' };

      // 获取所有子元素
      const allElements = policy.querySelectorAll('*');

      return {
        outerHTML: policy.outerHTML,
        innerHTML: policy.innerHTML,
        childElements: Array.from(allElements).map(el => ({
          tag: el.tagName.toLowerCase(),
          type: el.type || '',
          class: el.className,
          id: el.id,
          checked: el.checked,
          ariaChecked: el.getAttribute('aria-checked'),
          visible: el.offsetParent !== null,
          width: el.getBoundingClientRect().width,
          height: el.getBoundingClientRect().height,
          text: el.textContent?.substring(0, 30),
        })),
        // 查找所有复选框
        checkboxes: Array.from(policy.querySelectorAll('input[type="checkbox"]')).map(cb => ({
          id: cb.id,
          class: cb.className,
          checked: cb.checked,
          visible: cb.offsetParent !== null,
          style: cb.style.cssText,
        })),
      };
    });

    console.log("\n【协议容器 HTML】");
    console.log(structure.outerHTML);

    console.log("\n【所有子元素】");
    structure.childElements.forEach((el, i) => {
      if (el.width > 0 || el.type === 'checkbox') {
        console.log(`\n${i+1}. <${el.tag}${el.type ? ` type="${el.type}"` : ''}>`);
        console.log(`   class: "${el.class}"`);
        console.log(`   尺寸: ${el.width}x${el.height}`);
        console.log(`   checked: ${el.checked}`);
        console.log(`   visible: ${el.visible}`);
        if (el.text && el.text.trim()) {
          console.log(`   text: "${el.text}"`);
        }
      }
    });

    console.log("\n【复选框元素】");
    if (structure.checkboxes.length > 0) {
      structure.checkboxes.forEach((cb, i) => {
        console.log(`\n复选框 #${i+1}:`);
        console.log(`   id: "${cb.id}"`);
        console.log(`   class: "${cb.class}"`);
        console.log(`   checked: ${cb.checked}`);
        console.log(`   visible: ${cb.visible}`);
        console.log(`   style: "${cb.style}"`);
      });
    } else {
      console.log("   未找到 <input type='checkbox'>");
    }

    // 高亮显示
    await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      if (policy) {
        policy.style.border = '5px solid red';

        // 高亮所有子元素
        policy.querySelectorAll('*').forEach((el, i) => {
          if (el.offsetParent !== null) {
            el.style.outline = '2px solid blue';
            el.setAttribute('data-index', i+1);
          }
        });

        // 特别高亮复选框
        policy.querySelectorAll('input[type="checkbox"]').forEach(cb => {
          cb.style.outline = '5px solid lime';
          cb.style.outlineOffset = '3px';
        });
      }
    });

    console.log("\n✨ 浏览器中所有元素已高亮");
    console.log("   🔴 红色边框 = 协议容器");
    console.log("   🔵 蓝色边框 = 所有子元素");
    console.log("   🟢 绿色边框 = 复选框");

    console.log("\n⏸️  浏览器保持打开 60 秒...");
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("❌ 错误:", error.message);
  } finally {
    await browser.close();
  }
}

analyzeAgreementStructure().catch(console.error);
