// 在 clickVisualAgreementControl 函数中，如果找不到复选框控件，
// 应该直接点击容器本身，而不是返回 false

async function clickVisualAgreementControl(container) {
  return container
    .evaluate((element) => {
      const root = element.closest(".policy, label, div") || element.parentElement || element;

      // 1. 先尝试查找复选框控件
      const controls = [
        ...root.querySelectorAll(
          'input[type="checkbox"], [role="checkbox"], [class*="checkbox"], img, svg, [aria-checked]',
        ),
      ];

      for (const control of controls) {
        if (control.tagName.toLowerCase() === "a") {
          continue;
        }
        if (control.getAttribute("data-ai-testing-agreement-clicked") === "1") {
          return true;
        }
        if (control.getAttribute("aria-checked") === "true") {
          return true;
        }
        if (control instanceof HTMLInputElement && control.type === "checkbox" && control.checked) {
          return true;
        }
        control.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
        control.setAttribute("data-ai-testing-agreement-clicked", "1");
        return true;
      }

      // 2. 🔥 如果没有找到复选框控件，尝试查找可点击的视觉元素
      // 查找可能是复选框的元素（通过class名称或位置判断）
      const possibleCheckboxes = root.querySelectorAll('div, span, i, svg, img');
      for (const el of possibleCheckboxes) {
        const classList = Array.from(el.classList || []);
        const className = el.className || '';

        // 检查是否包含复选框相关的class名称
        if (
          classList.some(cls => /check|box|icon|select/i.test(cls)) ||
          /check|box|icon|select/i.test(className)
        ) {
          // 找到了疑似复选框的元素，点击它
          el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
          el.setAttribute("data-ai-testing-agreement-clicked", "1");
          return true;
        }
      }

      // 3. 🔥 最后的兜底方案：直接点击整个协议容器
      // 对于某些实现，点击文字区域就会触发复选框切换
      element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      element.setAttribute("data-ai-testing-agreement-clicked", "1");
      return true;
    })
    .catch(() => false);
}
