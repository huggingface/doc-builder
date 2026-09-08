// Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
// Source slicing stays in JavaScript: mdsvex offsets count UTF-16 code units.
const { compile } = require("mdsvex");
const { parse: parseSvelte } = require("svelte/compiler");
const fs = require("node:fs");

async function parse(source) {
	let tree;
	await compile(source, {
		highlight: false,
		smartypants: false,
		remarkPlugins: [
			() => (ast) => {
				tree = structuredClone(ast);
			},
		],
	});
	return tree;
}
function walk(node, fn) {
	fn(node);
	for (const child of node.children || []) walk(child, fn);
}
const start = (node) => node.position.start.offset;
const end = (node) => node.position.end.offset;
const title = (node) =>
	node.children?.length ? node.children.map(title).join(" ").trim() : (node.value || "").trim();
const slug = (node) =>
	title(node)
		.toLowerCase()
		.replace(/\s+/g, "-")
		.replace(/[^\p{L}\p{N}-]+/gu, "");
const url =
	/https?:\/\/(?:[^\s<>()\[\]{}"'`]|\([^\s<>]*?\))*(?:[^\s<>()\[\]{}"'`.,;:!?]|\([^\s<>]*?\))/g;
const escapeRE = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

async function extract(source, keep = []) {
	if (source.includes("¤")) throw Error("Source contains reserved translation marker ¤");
	let protectedSpans = [];
	function protect(a, b, block = false) {
		if (a >= b || protectedSpans.some((s) => a < s.b && b > s.a && !(a <= s.a && b >= s.b))) return;
		protectedSpans = protectedSpans.filter((s) => !(a <= s.a && b >= s.b));
		protectedSpans.push({ a, b, block });
	}
	const initial = await parse(source);
	walk(initial, (node) => {
		if (node.type === "link" && source[start(node)] === "<") protect(start(node), end(node));
		if (["code", "inlineCode", "yaml", "definition"].includes(node.type))
			protect(start(node), end(node), node.type !== "inlineCode");
	});
	// An exact heading/object match is an API identifier, not an English prose request.
	const headings = [];
	walk(initial, (n) => {
		if (n.type === "heading") headings.push(n);
	});
	for (let i = 0; i < headings.length; i++) {
		const node = headings[i],
			a = start(node.children[0]),
			b = end(node.children.at(-1));
		const following = source.slice(
			end(node),
			headings[i + 1] ? start(headings[i + 1]) : source.length
		);
		const match = following.match(/^[ \t]*\[\[autodoc\]\][ \t]+(\S+)/m);
		const label = source
			.slice(a, b)
			.replace(/\[\[[^\]]+\]\]$/, "")
			.trim();
		if (match && [match[1], match[1].split(".").at(-1), "transformers." + match[1]].includes(label))
			protect(a, b);
	}
	// Extensions recognized by doc-builder; ordinary Markdown is handled by mdsvex.
	const extensions = [
		[/<!--[^]*?-->/g, true],
		[/<(script|style|pre|code|literalinclude|include)\b[^>]*>[^]*?<\/\1\s*>/gi, true],
		[/^[ \t]*\[\[autodoc\]\][^\n]*(?:(?:\n[ \t]*)*\n[ \t]*-[ \t]+[^\n]*)*/gm, true],
		[/\[\[(?:literalinclude|include)\]\][^]*?\[\[\/(?:literalinclude|include)\]\]/g, true],
		[/\[\[[^\]\n]*\]\]/g, false],
		[/\[`[^`\n]+`\](?!\()/g, false],
		[/\$\$[^]*?\$\$/g, false],
		[/\\{1,2}\([^]*?\\{1,2}\)/g, false],
		[
			/(?<![\\$])\$(?:(?![\s$])(?:[^$\n]|\n(?![ \t]*\n)){0,200}?(?<![\s\\])|[ \t](?![\s$])(?:[^$\n]|\n(?![ \t]*\n)){0,200}?(?<![\s\\])[ \t])\$(?![\d$])/g,
			false,
		],
		[/<\/?[A-Za-z][\w:.-]*(?:\s+(?:[^<>"']|"[^"]*"|'[^']*')*)?\s*\/?>/g, false],
		[/\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/g, false],
		[/\b[A-Za-z][A-Za-z0-9]*_(?:[A-Za-z0-9]+_)*[A-Za-z0-9]+\b/g, false], // Literal snake_case identifiers.
		[/\{\\[A-Za-z]+\b/g, false], // TeX prose groups such as {\em Transient Global}.
	];
	for (const [pattern, block] of extensions)
		for (const m of source.matchAll(pattern)) protect(m.index, m.index + m[0].length, block);
	// Use Svelte's own grammar for nested expressions; never expose their identifiers as prose.
	for (const match of source.matchAll(/\{/g)) {
		const a = match.index;
		if (protectedSpans.some((s) => s.a <= a && a < s.b)) continue;
		const closing = source.slice(a).match(/^\{\/(if|each|await|key|snippet)\}/);
		if (closing) {
			protect(a, a + closing[0].length);
			continue;
		}

		for (let b = source.indexOf("}", a + 1); b >= 0; b = source.indexOf("}", b + 1)) {
			const raw = source.slice(a, b + 1),
				block = raw.match(/^\{#(if|each|await|key|snippet)\b/);
			const branch = raw.match(/^\{:(else|then|catch)\b/);
			const candidate = block
				? raw + `{/${block[1]}}`
				: branch
				? branch[1] === "else"
					? "{#if true}" + raw + "{/if}"
					: "{#await promise}" + raw + "{/await}"
				: raw;
			try {
				let nodes;
				try {
					nodes = parseSvelte(candidate).html.children;
				} catch {
					nodes = parseSvelte("{" + candidate + "}").html.children;
					if (nodes.length === 1 && nodes[0].start === 0 && nodes[0].end === candidate.length + 2) {
						protect(a, b + 1);
						break;
					}
				}

				if (nodes.length === 1 && nodes[0].start === 0 && nodes[0].end === candidate.length) {
					protect(a, b + 1);
					break;
				}
			} catch {
				/* A closing brace inside a string or nested expression is not its end. */
			}
		}
		// Unparseable braces are literal prose (for example {Pop, Piano Cover}).
	}
	// Raw URL labels and bare destinations are not always link nodes in mdsvex.
	for (const m of source.matchAll(url)) protect(m.index, m.index + m[0].length);
	for (const word of [...keep].sort((a, b) => b.length - a.length)) {
		const pattern = new RegExp(`(?<![A-Za-z0-9_])${escapeRE(word)}(?![A-Za-z0-9_])`, "giu");
		for (const m of source.matchAll(pattern)) protect(m.index, m.index + m[0].length);
	}
	protectedSpans.sort((a, b) => a.a - b.a);
	let cleaned = source;
	for (const s of [...protectedSpans].reverse()) {
		const raw = source.slice(s.a, s.b);
		const standalone =
			/^[ \t>]*$/.test(source.slice(source.lastIndexOf("\n", s.a - 1) + 1, s.a)) &&
			!source
				.slice(s.b, source.indexOf("\n", s.b) < 0 ? source.length : source.indexOf("\n", s.b))
				.trim();
		cleaned =
			cleaned.slice(0, s.a) +
			raw.replace(/[^\r\n]/g, s.block || standalone ? " " : "x") +
			cleaned.slice(s.b);
	}
	const tree = await parse(cleaned);
	const containers = [];
	walk(tree, (n) => {
		if (["paragraph", "heading", "tableCell"].includes(n.type) && n.children?.length)
			containers.push(n);
	});
	const units = [],
		pieces = [],
		literalEdits = [];
	let cursor = 0;
	for (const node of containers) {
		const a = start(node.children[0]),
			b = end(node.children.at(-1));
		if (a < cursor) throw Error("Overlapping prose containers");
		const spans = [];
		let pairId = 0;
		function add(x, y, kind = "opaque", pair = null) {
			if (x < y) spans.push({ a: x, b: y, kind, pair });
		}
		function inline(n) {
			const x = start(n),
				y = end(n);
			if (n.type === "text") return;
			if (
				["link", "linkReference", "emphasis", "strong", "delete"].includes(n.type) &&
				n.children?.length
			) {
				if (n.type === "link" && /^(?:https?:\/\/|<https?:\/\/)/.test(source.slice(x, y))) {
					add(x, y);
					return;
				}
				const id = pairId++;
				add(x, start(n.children[0]), "open", id);
				add(end(n.children.at(-1)), y, "close", id);
				for (const c of n.children) inline(c);
			} else if (["image", "imageReference"].includes(n.type)) {
				const raw = source.slice(x, y),
					id = pairId++;
				let close = 2,
					depth = 1;
				for (; close < raw.length; close++) {
					if (raw[close] === "\\") {
						close++;
						continue;
					}
					if (raw[close] === "[") depth++;
					if (raw[close] === "]" && --depth === 0) break;
				}
				if (depth) throw Error("Image has no label span");
				add(x, x + 2, "open", id);
				add(x + close, y, "close", id);
			} else add(x, y);
		}
		for (const c of node.children) inline(c);
		for (const s of protectedSpans) if (s.a >= a && s.b <= b) add(s.a, s.b);
		spans.sort((x, y) => x.a - y.a || y.b - x.b);
		const tokens = [];
		let text = "",
			pos = a;
		function token(raw, kind = "opaque", pair = null) {
			const id = tokens.length;
			tokens.push({ raw, kind, pair });
			return `¤${id}¤`;
		}
		function prose(raw, base) {
			// Keep literal Markdown syntax and continuation indentation out of generation too.
			return raw.replace(
				/\\[!"#$%&\x27()*+,\-./:;<=>?@[\]\\^_`{|}~]|\r?\n[ \t>]*|[\\`*_[\]{}<>|~!#$]/g,
				(m, offset) => {
					if (m === "_" || m === "*")
						literalEdits.push({ a: base + offset, b: base + offset + 1, text: "\\" + m });
					return token(m);
				}
			);
		}
		for (const s of spans) {
			if (s.a < pos) {
				if (s.b > pos) throw Error("Crossing protected spans");
				continue;
			}
			text += prose(source.slice(pos, s.a), pos) + token(source.slice(s.a, s.b), s.kind, s.pair);
			pos = s.b;
		}
		text += prose(source.slice(pos, b), pos);
		const tags = [];
		for (let i = 0; i < tokens.length; i++) {
			const m = tokens[i].raw.match(/^<(\/?)([A-Za-z][\w:.-]*)(?:\s[^]*)?\/?>(?:$)/);
			if (
				!m ||
				/\/>$/.test(tokens[i].raw) ||
				/^(?:img|br|hr|input|meta|link|source|wbr)$/i.test(m[2])
			)
				continue;
			if (!m[1]) tags.push({ name: m[2], index: i });
			else if (tags.at(-1)?.name === m[2]) {
				const open = tags.pop(),
					id = pairId++;
				Object.assign(tokens[open.index], { kind: "open", pair: id });
				Object.assign(tokens[i], { kind: "close", pair: id });
			}
		}
		pieces.push(source.slice(cursor, a));
		cursor = b;
		units.push({ text, tokens, kind: node.type });
	}
	pieces.push(source.slice(cursor));
	return { pieces, units, literalEdits };
}

async function normalize(source) {
	const tree = await parse(source),
		edits = [],
		headings = [],
		definitions = new Set();
	walk(tree, (n) => {
		if (n.type === "definition") definitions.add(n.identifier);
	});
	walk(tree, (n) => {
		if (
			["linkReference", "imageReference"].includes(n.type) &&
			definitions.has(n.identifier) &&
			n.referenceType !== "full"
		) {
			const raw = source.slice(start(n), end(n));
			edits.push({
				a: start(n),
				b: end(n),
				text: (n.referenceType === "collapsed" ? raw.slice(0, -2) : raw) + `[${n.label}]`,
			});
		}
	});
	walk(tree, (n) => {
		if (n.type === "heading") headings.push(n);
	});
	for (let i = 0; i < headings.length; i++) {
		const n = headings[i],
			raw = source.slice(start(n), end(n));
		// autodoc supplies the preceding heading's object ID during the normal build.
		const following = source.slice(
			end(n),
			headings[i + 1] ? start(headings[i + 1]) : source.length
		);
		if (/\[\[[^\]\n]+\]\]/.test(raw) || /\[\[autodoc\]\]/.test(following)) continue;
		const id = slug(n);
		if (!id) throw Error("Heading has no usable anchor: " + raw);
		edits.push({ a: end(n.children.at(-1)), b: end(n.children.at(-1)), text: `[[${id}]]` });
	}
	function urls(n, inLink = false) {
		const x = start(n),
			y = end(n),
			raw = source.slice(x, y);
		if (n.type === "link" && /^https?:\/\//.test(raw)) edits.push({ a: x, b: y, text: `<${raw}>` });
		if (n.type === "text" && !inLink)
			for (const m of raw.matchAll(url))
				edits.push({ a: x + m.index, b: x + m.index + m[0].length, text: `<${m[0]}>` });
		for (const c of n.children || []) urls(c, inLink || ["link", "linkReference"].includes(n.type));
	}
	urls(tree);
	for (const e of edits.sort((a, b) => b.a - a.a))
		source = source.slice(0, e.a) + e.text + source.slice(e.b);
	const { literalEdits } = await extract(source);
	for (const e of literalEdits.reverse())
		source = source.slice(0, e.a) + e.text + source.slice(e.b);
	return source;
}

async function main() {
	const input = JSON.parse(fs.readFileSync(0, "utf8"));
	const result = [];
	for (const page of input.pages) {
		const source = input.normalize ? await normalize(page) : page;
		result.push({ ...(await extract(source, input.keep)), source });
	}
	process.stdout.write(JSON.stringify(result));
}
main().catch((error) => {
	console.error(error.stack);
	process.exitCode = 1;
});
