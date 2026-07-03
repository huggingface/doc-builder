const removeAllCss = {
	postcssPlugin: "postcss-empty",
	OnceExit(root) {
		root.removeAll(); // This will remove all the nodes, effectively emptying the content.
	},
};

const plugins = [
	//Tailwind needs to run before other plugins,
	require("@tailwindcss/postcss"),
	//But others, like autoprefixer, need to run after,
	require("autoprefixer"),
];

// make the resulting CSS files empty during "build" process
// to not conflict with the already existing hub tailwind
if (process.argv.includes("build")) {
	plugins.push(removeAllCss);
}

const config = { plugins };

module.exports = config;
