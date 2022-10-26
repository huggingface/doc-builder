export const PIPELINE_DATA = {
	"text-classification": {
		name:     "Text Classification",
		subtasks: [
			{
				type: "acceptability-classification",
				name: "Acceptability Classification",
			},
			{
				type: "entity-linking-classification",
				name: "Entity Linking Classification",
			},
			{
				type: "fact-checking",
				name: "Fact Checking",
			},
			{
				type: "intent-classification",
				name: "Intent Classification",
			},
			{
				type: "multi-class-classification",
				name: "Multi Class Classification",
			},
			{
				type: "multi-label-classification",
				name: "Multi Label Classification",
			},
			{
				type: "multi-input-text-classification",
				name: "Multi-input Text Classification",
			},
			{
				type: "natural-language-inference",
				name: "Natural Language Inference",
			},
			{
				type: "semantic-similarity-classification",
				name: "Semantic Similarity Classification",
			},
			{
				type: "sentiment-classification",
				name: "Sentiment Classification",
			},
			{
				type: "topic-classification",
				name: "Topic Classification",
			},
			{
				type: "semantic-similarity-scoring",
				name: "Semantic Similarity Scoring",
			},
			{
				type: "sentiment-scoring",
				name: "Sentiment Scoring",
			},
			{
				type: "sentiment-analysis",
				name: "Sentiment Analysis",
			},
			{
				type: "hate-speech-detection",
				name: "Hate Speech Detection",
			},
			{
				type: "text-scoring",
				name: "Text Scoring",
			},
		],
		modality: "nlp",
		color:    "orange",
	},
	"token-classification": {
		name:     "Token Classification",
		subtasks: [
			{
				type: "named-entity-recognition",
				name: "Named Entity Recognition",
			},
			{
				type: "part-of-speech",
				name: "Part of Speech",
			},
			{
				type: "parsing",
				name: "Parsing",
			},
			{
				type: "lemmatization",
				name: "Lemmatization",
			},
			{
				type: "word-sense-disambiguation",
				name: "Word Sense Disambiguation",
			},
			{
				type: "coreference-resolution",
				name: "Coreference-resolution",
			},
		],
		modality: "nlp",
		color:    "blue",
	},
	"table-question-answering": {
		name:     "Table Question Answering",
		modality: "nlp",
		color:    "green",
	},
	"question-answering": {
		name:     "Question Answering",
		subtasks: [
			{
				type: "extractive-qa",
				name: "Extractive QA",
			},
			{
				type: "open-domain-qa",
				name: "Open Domain QA",
			},
			{
				type: "closed-domain-qa",
				name: "Closed Domain QA",
			},
		],
		modality: "nlp",
		color:    "blue",
	},
	"zero-shot-classification": {
		name:     "Zero-Shot Classification",
		modality: "nlp",
		color:    "yellow",
	},
	"translation": {
		name:     "Translation",
		modality: "nlp",
		color:    "green",
	},
	"summarization": {
		name:     "Summarization",
		subtasks: [
			{
				type: "news-articles-summarization",
				name: "News Articles Summarization",
			},
			{
				type: "news-articles-headline-generation",
				name: "News Articles Headline Generation",
			},
		],
		modality: "nlp",
		color:    "indigo",
	},
	"conversational": {
		name:     "Conversational",
		subtasks: [
			{
				type: "dialogue-generation",
				name: "Dialogue Generation",
			},
		],
		modality: "nlp",
		color:    "green",
	},
	"feature-extraction": {
		name:     "Feature Extraction",
		modality: "multimodal",
		color:    "red",
	},
	"text-generation": {
		name:     "Text Generation",
		subtasks: [
			{
				type: "dialogue-modeling",
				name: "Dialogue Modeling",
			},
			{
				type: "language-modeling",
				name: "Language Modeling",
			},
		],
		modality: "nlp",
		color:    "indigo",
	},
	"text2text-generation": {
		name:     "Text2Text Generation",
		subtasks: [
			{
				type: "text-simplification",
				name: "Text simplification",
			},
			{
				type: "explanation-generation",
				name: "Explanation Generation",
			},
			{
				type: "abstractive-qa",
				name: "Abstractive QA",
			},
			{
				type: "open-domain-abstractive-qa",
				name: "Open Domain Abstractive QA",
			},
			{
				type: "closed-domain-qa",
				name: "Closed Domain QA",
			},
			{
				type: "open-book-qa",
				name: "Open Book QA",
			},
			{
				type: "closed-book-qa",
				name: "Closed Book QA",
			},
		],
		modality: "nlp",
		color:    "indigo",
	},
	"fill-mask": {
		name:     "Fill-Mask",
		subtasks: [
			{
				type: "slot-filling",
				name: "Slot Filling",
			},
			{
				type: "masked-language-modeling",
				name: "Masked Language Modeling",
			},
		],
		modality: "nlp",
		color:    "red",
	},
	"sentence-similarity": {
		name:     "Sentence Similarity",
		modality: "nlp",
		color:    "yellow",
	},
	"text-to-speech": {
		name:     "Text-to-Speech",
		modality: "audio",
		color:    "yellow",
	},
	"automatic-speech-recognition": {
		name:     "Automatic Speech Recognition",
		modality: "audio",
		color:    "yellow",
	},
	"audio-to-audio": {
		name:     "Audio-to-Audio",
		modality: "audio",
		color:    "blue",
	},
	"audio-classification": {
		name:     "Audio Classification",
		subtasks: [
			{
				type: "keyword-spotting",
				name: "Keyword Spotting",
			},
			{
				type: "speaker-identification",
				name: "Speaker Identification",
			},
			{
				type: "audio-intent-classification",
				name: "Audio Intent Classification",
			},
			{
				type: "audio-emotion-recognition",
				name: "Audio Emotion Recognition",
			},
			{
				type: "audio-language-identification",
				name: "Audio Language Identification",
			},
		],
		modality: "audio",
		color:    "green",
	},
	"voice-activity-detection": {
		name:     "Voice Activity Detection",
		modality: "audio",
		color:    "red",
	},
	"image-classification": {
		name:     "Image Classification",
		subtasks: [
			{
				type: "multi-label-image-classification",
				name: "Multi Label Image Classification",
			},
			{
				type: "multi-class-image-classification",
				name: "Multi Class Image Classification",
			},
		],
		modality: "cv",
		color:    "blue",
	},
	"object-detection": {
		name:     "Object Detection",
		subtasks: [
			{
				type: "face-detection",
				name: "Face Detection",
			},
			{
				type: "vehicle-detection",
				name: "Vehicle Detection",
			},
		],
		modality: "cv",
		color:    "yellow",
	},
	"image-segmentation": {
		name:     "Image Segmentation",
		subtasks: [
			{
				type: "instance-segmentation",
				name: "Instance Segmentation",
			},
			{
				type: "semantic-segmentation",
				name: "Semantic Segmentation",
			},
			{
				type: "panoptic-segmentation",
				name: "Panoptic Segmentation",
			},
		],
		modality: "cv",
		color:    "green",
	},
	"text-to-image": {
		name:     "Text-to-Image",
		modality: "multimodal",
		color:    "yellow",
	},
	"image-to-text": {
		name:     "Image-to-Text",
		subtasks: [
			{
				type: "image-captioning",
				name: "Image Captioning",
			},
		],
		modality: "multimodal",
		color:    "red",
	},
	"image-to-image": {
		name:     "Image-to-Image",
		modality: "cv",
		color:    "indigo",
	},
	"unconditional-image-generation": {
		name:     "Unconditional Image Generation",
		modality: "cv",
		color:    "green",
	},
	"reinforcement-learning": {
		name:           "Reinforcement Learning",
		modality:       "rl",
		color:          "red",
		hideInDatasets: true,
	},
	"robotics": {
		name:     "Robotics",
		modality: "rl",
		subtasks: [
			{
				type: "grasping",
				name: "Grasping",
			},
			{
				type: "task-planning",
				name: "Task Planning",
			},
		],
		color:          "blue",
		hideInDatasets: true,
	},
	"tabular-classification": {
		name:     "Tabular Classification",
		modality: "tabular",
		subtasks: [
			{
				type: "tabular-multi-class-classification",
				name: "Tabular Multi Class Classification",
			},
			{
				type: "tabular-multi-label-classification",
				name: "Tabular Multi Label Classification",
			},
		],
		color: "blue",
	},
	"tabular-regression": {
		name:     "Tabular Regression",
		modality: "tabular",
		subtasks: [
			{
				type: "tabular-single-column-regression",
				name: "Tabular Single Column Regression",
			},
		],
		color: "blue",
	},
	"tabular-to-text": {
		name:     "Tabular to Text",
		modality: "tabular",
		subtasks: [
			{
				type: "rdf-to-text",
				name: "RDF to text",
			},
		],
		color:        "blue",
		hideInModels: true,
	},
	"table-to-text": {
		name:         "Table to Text",
		modality:     "nlp",
		color:        "blue",
		hideInModels: true,
	},
	"multiple-choice": {
		name:     "Multiple Choice",
		subtasks: [
			{
				type: "multiple-choice-qa",
				name: "Multiple Choice QA",
			},
			{
				type: "multiple-choice-coreference-resolution",
				name: "Multiple Choice Coreference Resolution",
			},
		],
		modality:     "nlp",
		color:        "blue",
		hideInModels: true,
	},
	"text-retrieval": {
		name:     "Text Retrieval",
		subtasks: [
			{
				type: "document-retrieval",
				name: "Document Retrieval",
			},
			{
				type: "utterance-retrieval",
				name: "Utterance Retrieval",
			},
			{
				type: "entity-linking-retrieval",
				name: "Entity Linking Retrieval",
			},
			{
				type: "fact-checking-retrieval",
				name: "Fact Checking Retrieval",
			},
		],
		modality:     "nlp",
		color:        "indigo",
		hideInModels: true,
	},
	"time-series-forecasting": {
		name:     "Time Series Forecasting",
		modality: "tabular",
		subtasks: [
			{
				type: "univariate-time-series-forecasting",
				name: "Univariate Time Series Forecasting",
			},
			{
				type: "multivariate-time-series-forecasting",
				name: "Multivariate Time Series Forecasting",
			},
		],
		color:        "blue",
		hideInModels: true,
	},
	"visual-question-answering": {
		name:     "Visual Question Answering",
		subtasks: [
			{
				type: "visual-question-answering",
				name: "Visual Question Answering",
			},
		],
		modality: "multimodal",
		color:    "red",
	},
	"document-question-answering": {
		name:     "Document Question Answering",
		subtasks: [
			{
				type: "document-question-answering",
				name: "Document Question Answering",
			},
		],
		modality:       "multimodal",
		color:          "blue",
		hideInDatasets: true,
	},
	"zero-shot-image-classification": {
		name:     "Zero-Shot Image Classification",
		modality: "cv",
		color:    "yellow",
	},
	"other": {
		name:         "Other",
		modality:     "other",
		color:        "blue",
		hideInModels: true,
	},
};