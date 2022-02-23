import Tooltip from "./TooltipFromAction.svelte";

const id = "docstring-tooltip";

export function tooltip(element: HTMLElement, txt: string): any {
	let tooltipComponent;
	function mouseOver(event: MouseEvent) {
		cleanPrevious();
		tooltipComponent = new Tooltip({
			props: {
				txt,
				x: event.pageX,
				y: event.pageY,
				id
			},
			target: document.body
		});
	}
	function mouseMove(event: MouseEvent) {
		tooltipComponent.$set({
			x: event.pageX,
			y: event.pageY
		});
	}
	function mouseLeave() {
		tooltipComponent.$destroy();
	}

	function cleanPrevious() {
		const tooltipComponent = document.getElementById(id);
		if (tooltipComponent) {
			tooltipComponent.parentNode?.removeChild(tooltipComponent);
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
		}
	};
}
