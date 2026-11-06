/**
 * UI strings of the "Copy page" menu (CopyLLMTxtMenu.svelte).
 *
 * Machine-translated pages (`doc-builder translate-docs`) run the JS of the English build, so the
 * language is read from the page URL at runtime (`/docs/{library}/[{version}/]{lang}/...`),
 * not from the build's DOCS_LANGUAGE.
 */
export interface CopyMenuStrings {
	copyPage: string;
	copied: string;
	copyPageDescription: string;
	viewMarkdown: string;
	viewMarkdownDescription: string;
	openIn: (app: string) => string;
	askQuestions: string;
	connectMcp: string;
	connectMcpDescription: string;
	menu: string;
	openMenu: string;
	closeMenu: string;
}

const STRINGS: Record<string, CopyMenuStrings> = {
	en: {
		copyPage: "Copy page",
		copied: "Copied",
		copyPageDescription: "Copy page as Markdown for LLMs",
		viewMarkdown: "View as Markdown",
		viewMarkdownDescription: "View this page as plain text",
		openIn: (app) => `Open in ${app}`,
		askQuestions: "Ask questions about this page",
		connectMcp: "Connect to MCP Client",
		connectMcpDescription: "Install MCP server on Cursor, VS Code, etc.",
		menu: "Copy menu",
		openMenu: "Open copy menu",
		closeMenu: "Close copy menu",
	},
	zh: {
		copyPage: "复制页面",
		copied: "已复制",
		copyPageDescription: "将页面复制为适用于 LLM 的 Markdown",
		viewMarkdown: "以 Markdown 查看",
		viewMarkdownDescription: "以纯文本查看此页面",
		openIn: (app) => `在 ${app} 中打开`,
		askQuestions: "就此页面提问",
		connectMcp: "连接到 MCP 客户端",
		connectMcpDescription: "在 Cursor、VS Code 等中安装 MCP 服务器",
		menu: "复制菜单",
		openMenu: "打开复制菜单",
		closeMenu: "关闭复制菜单",
	},
	ja: {
		copyPage: "ページをコピー",
		copied: "コピーしました",
		copyPageDescription: "LLM 向けに Markdown 形式でページをコピー",
		viewMarkdown: "Markdown で表示",
		viewMarkdownDescription: "このページをプレーンテキストで表示",
		openIn: (app) => `${app} で開く`,
		askQuestions: "このページについて質問する",
		connectMcp: "MCP クライアントに接続",
		connectMcpDescription: "Cursor や VS Code などに MCP サーバーをインストール",
		menu: "コピーメニュー",
		openMenu: "コピーメニューを開く",
		closeMenu: "コピーメニューを閉じる",
	},
	ko: {
		copyPage: "페이지 복사",
		copied: "복사됨",
		copyPageDescription: "LLM용 Markdown으로 페이지 복사",
		viewMarkdown: "Markdown으로 보기",
		viewMarkdownDescription: "이 페이지를 일반 텍스트로 보기",
		openIn: (app) => `${app}에서 열기`,
		askQuestions: "이 페이지에 대해 질문하기",
		connectMcp: "MCP 클라이언트에 연결",
		connectMcpDescription: "Cursor, VS Code 등에 MCP 서버 설치",
		menu: "복사 메뉴",
		openMenu: "복사 메뉴 열기",
		closeMenu: "복사 메뉴 닫기",
	},
	pt: {
		copyPage: "Copiar página",
		copied: "Copiado",
		copyPageDescription: "Copiar a página como Markdown para LLMs",
		viewMarkdown: "Ver como Markdown",
		viewMarkdownDescription: "Ver esta página como texto simples",
		openIn: (app) => `Abrir no ${app}`,
		askQuestions: "Fazer perguntas sobre esta página",
		connectMcp: "Conectar a um cliente MCP",
		connectMcpDescription: "Instalar o servidor MCP no Cursor, VS Code etc.",
		menu: "Menu de cópia",
		openMenu: "Abrir menu de cópia",
		closeMenu: "Fechar menu de cópia",
	},
	es: {
		copyPage: "Copiar página",
		copied: "Copiado",
		copyPageDescription: "Copiar la página como Markdown para LLM",
		viewMarkdown: "Ver como Markdown",
		viewMarkdownDescription: "Ver esta página como texto sin formato",
		openIn: (app) => `Abrir en ${app}`,
		askQuestions: "Hacer preguntas sobre esta página",
		connectMcp: "Conectar a un cliente MCP",
		connectMcpDescription: "Instalar el servidor MCP en Cursor, VS Code, etc.",
		menu: "Menú de copia",
		openMenu: "Abrir el menú de copia",
		closeMenu: "Cerrar el menú de copia",
	},
	fr: {
		copyPage: "Copier la page",
		copied: "Copié",
		copyPageDescription: "Copier la page en Markdown pour les LLM",
		viewMarkdown: "Afficher en Markdown",
		viewMarkdownDescription: "Afficher cette page en texte brut",
		openIn: (app) => `Ouvrir dans ${app}`,
		askQuestions: "Poser des questions sur cette page",
		connectMcp: "Connecter à un client MCP",
		connectMcpDescription: "Installer le serveur MCP dans Cursor, VS Code, etc.",
		menu: "Menu de copie",
		openMenu: "Ouvrir le menu de copie",
		closeMenu: "Fermer le menu de copie",
	},
	vi: {
		copyPage: "Sao chép trang",
		copied: "Đã sao chép",
		copyPageDescription: "Sao chép trang dưới dạng Markdown cho LLM",
		viewMarkdown: "Xem dạng Markdown",
		viewMarkdownDescription: "Xem trang này dưới dạng văn bản thuần",
		openIn: (app) => `Mở trong ${app}`,
		askQuestions: "Đặt câu hỏi về trang này",
		connectMcp: "Kết nối với ứng dụng MCP",
		connectMcpDescription: "Cài đặt máy chủ MCP trên Cursor, VS Code, v.v.",
		menu: "Menu sao chép",
		openMenu: "Mở menu sao chép",
		closeMenu: "Đóng menu sao chép",
	},
	id: {
		copyPage: "Salin halaman",
		copied: "Disalin",
		copyPageDescription: "Salin halaman sebagai Markdown untuk LLM",
		viewMarkdown: "Lihat sebagai Markdown",
		viewMarkdownDescription: "Lihat halaman ini sebagai teks biasa",
		openIn: (app) => `Buka di ${app}`,
		askQuestions: "Ajukan pertanyaan tentang halaman ini",
		connectMcp: "Hubungkan ke klien MCP",
		connectMcpDescription: "Pasang server MCP di Cursor, VS Code, dll.",
		menu: "Menu salin",
		openMenu: "Buka menu salin",
		closeMenu: "Tutup menu salin",
	},
	tr: {
		copyPage: "Sayfayı kopyala",
		copied: "Kopyalandı",
		copyPageDescription: "Sayfayı LLM'ler için Markdown olarak kopyala",
		viewMarkdown: "Markdown olarak görüntüle",
		viewMarkdownDescription: "Bu sayfayı düz metin olarak görüntüle",
		openIn: (app) => `${app} ile aç`,
		askQuestions: "Bu sayfa hakkında soru sor",
		connectMcp: "MCP istemcisine bağlan",
		connectMcpDescription: "MCP sunucusunu Cursor, VS Code vb. araçlara kur",
		menu: "Kopyalama menüsü",
		openMenu: "Kopyalama menüsünü aç",
		closeMenu: "Kopyalama menüsünü kapat",
	},
	ru: {
		copyPage: "Копировать страницу",
		copied: "Скопировано",
		copyPageDescription: "Скопировать страницу в формате Markdown для LLM",
		viewMarkdown: "Просмотреть как Markdown",
		viewMarkdownDescription: "Просмотреть эту страницу как обычный текст",
		openIn: (app) => `Открыть в ${app}`,
		askQuestions: "Задать вопросы об этой странице",
		connectMcp: "Подключить MCP-клиент",
		connectMcpDescription: "Установить MCP-сервер в Cursor, VS Code и др.",
		menu: "Меню копирования",
		openMenu: "Открыть меню копирования",
		closeMenu: "Закрыть меню копирования",
	},
	ar: {
		copyPage: "نسخ الصفحة",
		copied: "تم النسخ",
		copyPageDescription: "نسخ الصفحة بتنسيق Markdown للنماذج اللغوية الكبيرة",
		viewMarkdown: "عرض بتنسيق Markdown",
		viewMarkdownDescription: "عرض هذه الصفحة كنص عادي",
		openIn: (app) => `فتح في ${app}`,
		askQuestions: "اطرح أسئلة حول هذه الصفحة",
		connectMcp: "الاتصال بعميل MCP",
		connectMcpDescription: "ثبّت خادم MCP على Cursor وVS Code وغيرها",
		menu: "قائمة النسخ",
		openMenu: "فتح قائمة النسخ",
		closeMenu: "إغلاق قائمة النسخ",
	},
};

/** Strings for the language of the doc page at `pathname` (English when it has none of the above). */
export function copyMenuStrings(pathname: string): CopyMenuStrings {
	// "", "docs" | "learn", library, [version], lang, ...page (same rules as hfDocPaths.js)
	const params = pathname.split("/").slice(3);
	if (/^(?:(master|main)|v[\d.]+(rc\d+)?|pr_\d+)$/.test(params[0] ?? "")) {
		params.shift();
	}
	return STRINGS[params[0] ?? ""] ?? STRINGS.en;
}
