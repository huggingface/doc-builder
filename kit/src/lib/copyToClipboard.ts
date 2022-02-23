export function copyToClipboard(value: string): void {
	const textArea = document.createElement("textarea");
	document.body.appendChild(textArea);
	textArea.value = value;
	textArea.select();
	document.execCommand("copy");
	document.body.removeChild(textArea);
}
