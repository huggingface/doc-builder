const tailwindcss = require("tailwindcss");
const autoprefixer = require("autoprefixer");
const postcss = require("postcss");

const removeAllCss = postcss.plugin("postcss-empty", () => {
	return (root) => {
		root.removeAll(); // This will remove all the nodes, effectively emptying the content.
	};
});

const plugins = [
	//Some plugins, like tailwindcss/nesting, need to run before Tailwind,
	tailwindcss(),
	//But others, like autoprefixer, need to run after,
	autoprefixer,
];

// make the resulting CSS files empty during "build" process
// to not conflict with the already existing hub tailwind
if (process.argv.includes("build")) {
	plugins.push(removeAllCss);
}

const config = { plugins };

module.exports = config;
