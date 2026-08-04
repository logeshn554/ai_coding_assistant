/**
 * Copies the given text to the clipboard.
 * Uses the modern navigator.clipboard API if available,
 * and falls back to a hidden textarea with document.execCommand('copy')
 * for older browsers or non-secure (HTTP) contexts.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      console.warn('navigator.clipboard failed, falling back to document.execCommand', e);
    }
  }

  // Fallback for non-secure contexts or older browsers
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    // Avoid scrolling to bottom or impacting layout
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    return successful;
  } catch (err) {
    console.error('Fallback copy to clipboard failed:', err);
    return false;
  }
}
