export function copyToClipboard(value: string): void {
    const isRTL = document.documentElement.getAttribute('dir') === 'rtl';

    //To create a textarea element
    const textArea = document.createElement('textarea');
    textArea.value = value;

    //To style the textarea to be offscreen
    textArea.style.position = 'absolute';
    textArea.style.left = '-9999px';

    //To append the textarea to the body
    document.body.appendChild(textArea);

    //To select the textarea content
    textArea.select();

    //To copy the selected content to clipboard
    document.execCommand('copy');

    //To remove the textarea from the body
    document.body.removeChild(textArea);
}
