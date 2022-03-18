<script lang="ts">
	import { onMount } from "svelte";

	import { answers } from "./stores";

	export let choices: Choice[];

	interface Choice {
		text: string;
		explain: string;
		correct?: boolean;
		selected?: boolean;
	}

	const id = randomId();

	let isFalse: boolean = false;
	let isIncomplete: boolean = false;
	let selected: number[] = [];
	let submitted: number[] = [];

	onMount(() => {
		$answers = { ...$answers, [id]: { correct: false } };
	});

	function checkAnswer() {
		isFalse = false;
		isIncomplete = false;

		for (let i = 0; i < choices.length; i++) {
			const c = choices[i];
			if (c.correct && !selected.includes(i)) {
				isIncomplete = true;
			} else if (!c.correct && selected.includes(i)) {
				isFalse = true;
			}
		}
		submitted = selected;
		$answers = { ...$answers, [id]: { correct: !isIncomplete && !isFalse } };
		const isChapterComplete = Object.values($answers).every(({ correct }) => correct);
		if (isChapterComplete) {
			const event = new Event("ChapterComplete");
			window.dispatchEvent(event);
		}
	}

	function randomId(prefix = "_"): string {
		// Return a unique-ish random id string
		// Math.random should be unique because of its seeding algorithm.
		// Convert it to base 36 (numbers + letters), and grab the first 9 characters
		// after the decimal.
		return `${prefix}${Math.random().toString(36).substr(2, 9)}`;
	}
</script>

<div>
	<form on:submit|preventDefault={() => checkAnswer()}>
		{#each choices as choice, index}
			<label class="block">
				<input
					autocomplete="off"
					bind:group={selected}
					class="form-input -mt-1.5 mr-2"
					name="choice"
					type="checkbox"
					value={index}
				/>
				{@html choice.text}
			</label>
			{#if submitted && submitted.includes(index)}
				<div
					class="alert alert-{!!choice.correct ? 'success' : 'error'} mt-1 mb-2.5 leading-normal"
				>
					<span class="font-bold">
						{!!choice.correct ? "Correct!" : "Incorrect."}
					</span>
					{@html choice.explain}
				</div>
			{/if}
		{/each}
		<div class="flex flex-row items-center mt-3">
			<button class="btn px-4 mr-4" type="submit" disabled={!selected.length}> Submit </button>

			{#if submitted.length}
				<div class="font-semibold leading-snug">
					{#if isFalse}
						<span class="text-red-900 dark:text-red-200">
							Looks like at least one of your answers is wrong, try again!
						</span>
					{:else if isIncomplete}
						<span class="text-red-900 dark:text-red-200">
							You didn't select all the correct answers, there's more!
						</span>
					{:else}
						<span class="text-green-900 dark:text-green-200"> You got all the answers! </span>
					{/if}
				</div>
			{/if}
		</div>
	</form>
</div>
