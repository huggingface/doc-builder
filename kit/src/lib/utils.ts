export function updateQueryParamAndReplaceHistory(key: string, value: string) {
	// 1. Parse the current URL.
	const currentUrl = new URL(window.location.href);
	// 2. Use URLSearchParams to manipulate the query parameters.
	const searchParams = new URLSearchParams(currentUrl.search);
	// 3. Update the specific query parameter.
	searchParams.set(key, value);
	// 4. Construct the new URL.
	currentUrl.search = searchParams.toString();
	// 5. Push the new URL to browser's history.
	history.replaceState(null, "", currentUrl.toString());
}

export function getQueryParamValue(key: string) {
	// 1. Parse the current URL.
	const currentUrl = new URL(window.location.href);
	// 2. Use URLSearchParams to get the value of the specified query parameter.
	const searchParams = new URLSearchParams(currentUrl.search);
	return searchParams.get(key); // This will return the value or null if the key is not found.
}
