<script lang="ts">
	import { PIPELINE_DATA } from "./pipeline";

	import IconAudioClassification from "./PipelineIcons/IconAudioClassification.svelte";
	import IconAudioToAudio from "./PipelineIcons/IconAudioToAudio.svelte";
	import IconAutomaticSpeechRecognition from "./PipelineIcons/IconAutomaticSpeechRecognition.svelte";
	import IconConversational from "./PipelineIcons/IconConversational.svelte";
	import IconFeatureExtraction from "./PipelineIcons/IconFeatureExtraction.svelte";
	import IconFillMask from "./PipelineIcons/IconFillMask.svelte";
	import IconImageClassification from "./PipelineIcons/IconImageClassification.svelte";
	import IconImageSegmentation from "./PipelineIcons/IconImageSegmentation.svelte";
	import IconObjectDetection from "./PipelineIcons/IconObjectDetection.svelte";
	import IconQuestionAnswering from "./PipelineIcons/IconQuestionAnswering.svelte";
	import IconSentenceSimilarity from "./PipelineIcons/IconSentenceSimilarity.svelte";
	import IconTabularClassification from "./PipelineIcons/IconTabularClassification.svelte";
	import IconTabularRegression from "./PipelineIcons/IconTabularRegression.svelte";
	import IconSummarization from "./PipelineIcons/IconSummarization.svelte";
	import IconTableQuestionAnswering from "./PipelineIcons/IconTableQuestionAnswering.svelte";
	import IconText2textGeneration from "./PipelineIcons/IconText2textGeneration.svelte";
	import IconTextClassification from "./PipelineIcons/IconTextClassification.svelte";
	import IconTextGeneration from "./PipelineIcons/IconTextGeneration.svelte";
	import IconTextToImage from "./PipelineIcons/IconTextToImage.svelte";
	import IconImageToText from "./PipelineIcons/IconImageToText.svelte";
	import IconTextToSpeech from "./PipelineIcons/IconTextToSpeech.svelte";
	import IconTokenClassification from "./PipelineIcons/IconTokenClassification.svelte";
	import IconTranslation from "./PipelineIcons/IconTranslation.svelte";
	import IconVoiceActivityDetection from "./PipelineIcons/IconVoiceActivityDetection.svelte";
	import IconZeroShotClassification from "./PipelineIcons/IconZeroShotClassification.svelte";
	import IconReinforcementLearning from "./PipelineIcons/IconReinforcementLearning.svelte";
	import IconRobotics from "./PipelineIcons/IconRobotics.svelte";
	import IconImageToImage from "./PipelineIcons/IconImageToImage.svelte";
	import IconUnconditionalImageGeneration from "./PipelineIcons/IconUnconditionalImageGeneration.svelte";
	import IconDocumentQuestionAnswering from "./PipelineIcons/IconDocumentQuestionAnswering.svelte";

	export let classNames = "";
	export let pipeline = "";

	type SvelteComponent = typeof IconTextClassification;

	const ICON_COMPONENTS: Record<string, SvelteComponent> = {
		/// Keep same order as in huggingface_hub/Types.ts
		/// for easy mapping.
		"text-classification": IconTextClassification,
		"token-classification": IconTokenClassification,
		"table-question-answering": IconTableQuestionAnswering,
		"question-answering": IconQuestionAnswering,
		"zero-shot-classification": IconZeroShotClassification,
		translation: IconTranslation,
		summarization: IconSummarization,
		conversational: IconConversational,
		"feature-extraction": IconFeatureExtraction,
		"text-generation": IconTextGeneration,
		"text2text-generation": IconText2textGeneration,
		"fill-mask": IconFillMask,
		"sentence-similarity": IconSentenceSimilarity,
		"text-to-speech": IconTextToSpeech,
		"automatic-speech-recognition": IconAutomaticSpeechRecognition,
		"audio-to-audio": IconAudioToAudio,
		"audio-classification": IconAudioClassification,
		"voice-activity-detection": IconVoiceActivityDetection,
		"image-classification": IconImageClassification,
		"object-detection": IconObjectDetection,
		"image-segmentation": IconImageSegmentation,
		"text-to-image": IconTextToImage,
		"image-to-text": IconImageToText,
		"image-to-image": IconImageToImage,
		"unconditional-image-generation": IconUnconditionalImageGeneration,
		"reinforcement-learning": IconReinforcementLearning,
		robotics: IconRobotics,
		"tabular-classification": IconTabularClassification,
		"tabular-regression": IconTabularRegression,
		"document-question-answering": IconDocumentQuestionAnswering,
	};

	const PIPELINE_TAG_ICO_CLASS = Object.fromEntries(
		Object.entries(PIPELINE_DATA).map(([tagType, data]) => [tagType, `tag-ico-${data.color}`])
	);
</script>

<svelte:component
	this={ICON_COMPONENTS[pipeline] ?? IconFillMask}
	classNames="{classNames} tag-ico {PIPELINE_TAG_ICO_CLASS[pipeline]}"
/>
