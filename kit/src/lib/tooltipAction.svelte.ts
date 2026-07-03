import { mount, unmount } from "svelte";
import Tooltip from "./TooltipFromAction.svelte";

const id = "docstring-tooltip";

export function tooltip(element: HTMLElement, txt: string) {
	let tooltipComponent: Record<string, unknown> | undefined;
	const props = $state({ txt, x: 0, y: 0, id });

	function mouseOver(event: MouseEvent) {
		cleanPrevious();
		props.x = event.pageX;
		props.y = event.pageY;
		tooltipComponent = mount(Tooltip, {
			target: document.body,
			props,
		});
	}
	function mouseMove(event: MouseEvent) {
		props.x = event.pageX;
		props.y = event.pageY;
	}
	function mouseLeave() {
		if (tooltipComponent) {
			unmount(tooltipComponent);
			tooltipComponent = undefined;
		}
	}

	function cleanPrevious() {
		const previousTooltip = document.getElementById(id);
		if (previousTooltip) {
			previousTooltip.parentNode?.removeChild(previousTooltip);
		}
	}

	element.addEventListener("mouseover", mouseOver);
	element.addEventListener("mouseleave", mouseLeave);
	element.addEventListener("mousemove", mouseMove);

	return {
		destroy() {
			element.removeEventListener("mouseover", mouseOver);
			element.removeEventListener("mouseleave", mouseLeave);
			element.removeEventListener("mousemove", mouseMove);
		},
	};
}
