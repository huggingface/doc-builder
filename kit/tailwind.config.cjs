const defaultTheme = require("tailwindcss/defaultTheme");
const colors = require("tailwindcss/colors");

module.exports = {
	content: ["./src/**/*.{svelte,ts,mdx}"],

	darkMode: "class",
	theme: {
		container: {
			center: true,
			padding: { DEFAULT: "1rem" }
		},
		extend: {
			colors: {
				orange: colors.orange,
				teal: colors.teal,
				sky: colors.sky,
				violet: colors.violet,
				fuchsia: colors.fuchsia,
				pink: colors.pink,
				lime: colors.lime,
				cyan: colors.cyan,
				gray: {
					350: "#b3bcc9",
					// Dark blue
					// 925: '#131f3d',
					// 950: '#0a1226',
					// Darker
					850: "#141c2e",
					925: "#101623",
					950: "#0b0f19"
					// Darkest
					// 925: '#081122',
					// 950: '#000511',
				}
			},
			maxWidth: {
				"2xs": "16rem"
			},
			screens: {
				"with-hover": { raw: "(hover: hover)" },
				"no-hover": { raw: "(hover: none)" }
			},
			gridTemplateRows: {
				full: "100%"
			},
			fontFamily: {
				sans: ["Source Sans Pro", ...defaultTheme.fontFamily.sans],
				mono: ["IBM Plex Mono", ...defaultTheme.fontFamily.mono],
				serif: ["Charter", ...defaultTheme.fontFamily.serif]
			},
			fontSize: {
				smd: "0.94rem"
			},
			typography: (theme) => ({
				light: {
					css: [
						{
							color: theme("colors.gray.350"),
							'[class~="lead"]': {
								color: theme("colors.gray.300")
							},
							a: {
								color: theme("colors.gray.300")
							},
							strong: {
								color: theme("colors.gray.300")
							},
							"ol > li::before": {
								color: theme("colors.gray.400")
							},
							"ul > li::before": {
								backgroundColor: theme("colors.gray.600")
							},
							hr: {
								borderColor: theme("colors.gray.200")
							},
							blockquote: {
								color: theme("colors.gray.200"),
								borderLeftColor: theme("colors.gray.600")
							},
							h1: {
								color: theme("colors.gray.200")
							},
							h2: {
								color: theme("colors.gray.200")
							},
							h3: {
								color: theme("colors.gray.200")
							},
							h4: {
								color: theme("colors.gray.200")
							},
							"figure figcaption": {
								color: theme("colors.gray.400")
							},
							code: {
								color: theme("colors.gray.300")
							},
							"a code": {
								color: theme("colors.gray.300")
							},
							pre: {
								color: theme("colors.gray.300"),
								backgroundColor: theme("colors.gray.925")
							},
							thead: {
								color: theme("colors.gray.200"),
								borderBottomColor: theme("colors.gray.400")
							},
							"tbody tr": {
								borderBottomColor: theme("colors.gray.600")
							}
						}
					]
				},
				DEFAULT: {
					css: {
						color: colors.gray[600],
						maxWidth: "100%",
						fontSize: "1.05rem",
						h1: {
							fontSize: theme("fontSize.xl")[0],
							color: theme("colors.gray.700"),
							marginBottom: "1.7rem",
							fontWeight: 600
						},
						h2: {
							fontSize: theme("fontSize.xl")[0],
							color: theme("colors.gray.700"),
							fontWeight: 600
						},

						h3: {
							fontSize: theme("fontSize.xl")[0],
							color: theme("colors.gray.700"),
							fontWeight: 600
						},
						h4: {
							fontSize: theme("fontSize.lg")[0],
							color: theme("colors.gray.700"),
							fontWeight: 600
						},
						pre: {
							color: "currentColor",
							backgroundColor: theme("colors.gray.50")
						}
					}
				}
			}),
			zIndex: {
				5: "5",
				2: "2",
				1: "1",
				"-1": "-1"
			}
		}
	},
	plugins: [
		require("@tailwindcss/forms"),
		require("@tailwindcss/typography"),
		require("@tailwindcss/line-clamp"),
		require("@tailwindcss/aspect-ratio")
	]
};
