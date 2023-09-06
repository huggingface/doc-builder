<script lang="ts">
    import {onMount} from "svelte";
    import Tip from "$lib/Tip.svelte";
    import Youtube from "$lib/Youtube.svelte";
    import Docstring from "$lib/Docstring.svelte";
    import CodeBlock from "$lib/CodeBlock.svelte";
    import CodeBlockFw from "$lib/CodeBlockFw.svelte";
    import DocNotebookDropdown from "$lib/DocNotebookDropdown.svelte";
    import CourseFloatingBanner from "$lib/CourseFloatingBanner.svelte";
    import IconCopyLink from "$lib/IconCopyLink.svelte";
    import FrameworkContent from "$lib/FrameworkContent.svelte";
    import Markdown from "$lib/Markdown.svelte";
    import Question from "$lib/Question.svelte";
    import FrameworkSwitchCourse from "$lib/FrameworkSwitchCourse.svelte";
    import InferenceApi from "$lib/InferenceApi.svelte";
    import TokenizersLanguageContent from "$lib/TokenizersLanguageContent.svelte";
    import ExampleCodeBlock from "$lib/ExampleCodeBlock.svelte";
    import Added from "$lib/Added.svelte";
    import Changed from "$lib/Changed.svelte";
    import Deprecated from "$lib/Deprecated.svelte";
    import PipelineIcon from "$lib/PipelineIcon.svelte";
    import PipelineTag from "$lib/PipelineTag.svelte";
    let fw: "pt" | "tf" = "pt";
    onMount(() => {
        const urlParams = new URLSearchParams(window.location.search);
        fw = urlParams.get("fw") || "pt";
    });
</script>
    
### Running with `torch < 2.0`


<h2 class="bg-red-500"> My Test </h2>
