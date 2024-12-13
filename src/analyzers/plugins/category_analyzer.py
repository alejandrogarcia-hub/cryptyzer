"""
This module contains the category analyzer plugin for the repository analyzer.
"""

from collections import deque
import json
from typing import Any, Dict, List
import asyncio
import time

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from tiktoken import Encoding


from analyzers.models import PullRequestType
from config import settings, logger


class CategoryAnalyzerPlugin:
    """Base class for category analyzer plugins."""

    async def categorize(self, data: Any, feature_labels: List[str]) -> Dict[str, Any]:
        """Categorize the given data."""
        pass

    async def categorize_all(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[Dict]:
        """Categorize all the given data."""
        pass

    async def categorize_batch(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[Any]:
        """Categorize the given data."""
        pass


class PRTypeCategoryAnalyzerPlugin(CategoryAnalyzerPlugin):
    async def categorize_all(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[Dict]:
        """This process all data in a single batch but it is rate limited.

        Args:
            prs_data (List[Dict]): List of pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            List[Dict]: List of classified PRs
        """

        return [self.categorize(data, feature_labels) for data in prs_data]

    def categorize(self, data: Dict, feature_labels: List[str]) -> Dict[str, Any]:
        """
        Categorize pull request type based on metadata.

        Args:
            data (Dict): Pull request data
            feature_labels (List[str]): Available PR type labels

        Example:
            data = {
                "pr_number": 123,
                "title": "Add new feature",
                "body": "This is a new feature",
                "labels": ["feature", "enhancement"]
            }

        Returns:
            Dict[str, Any]: Classified pull request type based on content and labels.
        """
        title_lower = data["title"].lower()
        combined_text = f"{title_lower} {data['body'].lower() if data['body'] else ''}"
        labels_lower = [label.lower() for label in data["labels"]]

        result = None
        # Check labels first
        for label in labels_lower:
            if "feature" in label or "enhancement" in label:
                result = PullRequestType.FEATURE
            elif "bug" in label or "bugfix" in label:
                result = PullRequestType.BUGFIX
            elif "hotfix" in label or "critical" in label or "urgent" in label:
                result = PullRequestType.HOTFIX
            elif "test" in label or "testing" in label:
                result = PullRequestType.TEST
            elif "issue" in label:
                result = PullRequestType.ISSUE

        # Check title and body
        if any(
            keyword in combined_text for keyword in ["feature", "feat", "enhancement"]
        ):
            result = PullRequestType.FEATURE
        elif any(keyword in combined_text for keyword in ["fix", "bug", "issue #"]):
            result = PullRequestType.BUGFIX
        elif any(
            keyword in combined_text for keyword in ["hotfix", "critical", "urgent"]
        ):
            result = PullRequestType.HOTFIX
        elif any(keyword in combined_text for keyword in ["test", "testing"]):
            result = PullRequestType.TEST
        elif any(
            keyword in combined_text
            for keyword in ["refactor", "refactoring", "refact"]
        ):
            result = PullRequestType.REFACTOR
        elif "issue" in combined_text or "#" in title_lower:
            result = PullRequestType.ISSUE

        return {
            "pr_number": data["pr_number"],
            "pr_type": result.value if result else PullRequestType.OTHER.value,
        }


class LLMPRTypeCategoryAnalyzerPlugin(CategoryAnalyzerPlugin):
    """
    LLM-based repository analyzer using OpenAI's GPT models.

    Analyzes repository data using LLM to classify PRs and generate metrics.
    Includes token counting and management.

    Attributes:
        intervals (List[int]): Time intervals for analysis in days
        client (AsyncOpenAI): OpenAI API client
        encoding (tiktoken.Encoding): Token encoder for the specified model
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        encoding: Encoding,
        max_requests: int,
        max_tokens: int,
        period: float,
        data_dir: str,
    ):
        """
        Initialize the LLM analyzer.

        Args:
            client (AsyncOpenAI): OpenAI API client
        """
        self.client = client
        self.encoding = encoding
        self.data_dir = data_dir
        self.request_times = deque()
        self.token_counts = deque()
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.period = period
        self.temperature = 0.1

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using the model's tokenizer.

        Args:
            text (str): Text to count tokens for

        Returns:
            int: Number of tokens in text
        """
        return len(self.encoding.encode(text))

    async def _rate_limit(self, token_count: int = 0):
        """
        Rate limit the requests to the OpenAI API.
        This is to avoid rate limiting and ensure that we don't overload the API.
        Handles both request rate limits and token rate limits.

        Args:
            token_count (int): Number of tokens in the current request
        """
        try:
            now = time.monotonic()

            # Remove timestamps and token counts older than the allowed period
            while self.request_times and (now - self.request_times[0]) > self.period:
                self.request_times.popleft()
                if self.token_counts:  # Remove corresponding token count
                    self.token_counts.popleft()

            # Check both request count and token count limits
            while len(self.request_times) >= self.max_requests or (
                self.token_counts
                and sum(self.token_counts) + token_count > self.max_tokens
            ):
                # Calculate wait times for both limits
                request_wait_time = 0
                token_wait_time = 0

                if len(self.request_times) >= self.max_requests:
                    request_wait_time = self.period - (now - self.request_times[0])
                    logger.debug(
                        f"Request count limit reached. Waiting for {request_wait_time} seconds."
                    )

                if (
                    self.token_counts
                    and sum(self.token_counts) + token_count > self.max_tokens
                ):
                    token_wait_time = self.period - (now - self.request_times[0])
                    logger.debug(
                        f"Token count limit reached. Waiting for {token_wait_time} seconds."
                    )

                # Wait for the longer of the two wait times
                wait_time = max(request_wait_time, token_wait_time)
                logger.debug(f"Waiting for {wait_time} seconds.")
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

                # Update time and clean up old entries again
                now = time.monotonic()
                while (
                    self.request_times and (now - self.request_times[0]) > self.period
                ):
                    self.request_times.popleft()
                    if self.token_counts:
                        self.token_counts.popleft()

            # Record current request and token count
            self.request_times.append(now)
            self.token_counts.append(token_count)
        except Exception as e:
            logger.error(
                {
                    "message": "Error rate limiting",
                    "error": str(e),
                    "error_line": e.__traceback__.tb_lineno,
                }
            )
            raise e

    def _prepare_pr_prompt(self, pr_data: Dict, feature_labels: List[str]) -> str:
        """
        Prepare prompt for PR classification.

        Args:
            pr_data (Dict): Pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            str: Formatted prompt for the LLM
        """
        return f"""Analyze this pull request and classify it into one of these categories: {', '.join(feature_labels)}.
        {{
            "pr_number": {pr_data["pr_number"]},
            "title": {pr_data["title"]},
            "body": {pr_data["body"] if pr_data["body"] else 'No description'},
            "labels": {', '.join(pr_data["labels"])}
        }}
        """

    async def categorize_all(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[Dict]:
        """This process all data in a single batch but it is rate limited.

        Args:
            prs_data (List[Dict]): List of pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            List[Dict]: List of classified PRs
        """

        async def rate_limited_categorize(pr_info, feature_labels):
            # Enforce rate limit before making request
            prompt = self._prepare_pr_prompt(pr_info, feature_labels)
            token_count = self._count_tokens(prompt) + 300
            await self._rate_limit(token_count)
            return await self.categorize(pr_info, feature_labels)

        tasks = [rate_limited_categorize(data, feature_labels) for data in prs_data]
        pr_types = await asyncio.gather(*tasks)
        return pr_types

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def categorize(self, data: Dict, feature_labels: List[str]) -> Dict[str, Any]:
        """
        Classify a single pull request using LLM.

        Args:
            data (Dict): Pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            Dict[str, Any]: Classified PR type

        Raises:
            Exception: If classification fails
        """
        prompt = self._prepare_pr_prompt(data, feature_labels)
        token_count = self._count_tokens(prompt)
        logger.debug(f"Prompt token count: {token_count}")

        system_prompt = f"""You are a Staff Software Engineer at one of the top tech companies. 
        You will analyze a pull request and classify it into one of these categories: 
        {', '.join(feature_labels)}.
        You will be provided with input as:
        {{
            "pr_number": <number>,
            "title": <text>,
            "body": <text>,
            "labels": [<list of strings>]
        }}
        
        , and do your best to understand and infer a category other than "other". When you are not sure, output "other". 
        Output a string containing the following information: "pr_number,category"
        - pr_number is the same as the input pr_number
        - category is your assigment category to the PR and must be one of the categories in the list
        """

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=10,  # if you see the output truncated, increase this number
                timeout=120,
            )

            content = response.choices[0].message.content.strip().split(",")
            return {"pr_number": content[0], "pr_type": content[1]}
        except Exception as e:
            logger.error(
                {
                    "message": "Error classifying PR",
                    "error": str(e),
                    "error_line": e.__traceback__.tb_lineno,
                }
            )
            raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def categorize_batch(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[str]:
        """
        Classify multiple pull requests in batches. This is a good way to save some money, the API costs are half asof today (13/12/2024)
        The only problem is that the response is only guaranteed to comeback in 24 hours (completion_window="24h") ...
        it usally takes a lot less but responses come on 10 of minutes to hours. There is no other way to get the results faster.
        Left the implementation for future reference.

        Args:
            prs_data (List[Dict]): List of pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            List[str]: List of classifications in the same order as input PRs

        Raises:
            Exception: If batch processing fails
        """
        system_prompt = f"""You are a Staff Software Engineer at one of the top tech companies. 
        You will analyze multiple pull requests and classify each one into one of these categories: 
        {', '.join(feature_labels)}.
        You will be provided with input as:
        {{
            "pr_number": <number>,
            "title": <text>,
            "body": <text>,
            "labels": [<list of strings>]
        }}
        
        where number is an integer and text is a string. Please, do your best to understand and infer a category other than "other". 
        When you are not sure, output the category "other". You will output a json object containing the following information:
        {{"pr_number":<number>,"pr_type":<text>}}
        
        Respond with exactly one json object per line.
        - number is an integer and text is a string.
        - pr_number is the same as the input pr_number
        - pr_type is your assigment category to the PR and must be one of the categories in the list
        """

        logger.info(f"processing in a single batch {len(prs_data)} PRs")
        tasks = []
        for data in prs_data:
            task = {
                "custom_id": f"task-{data['row']}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    # This is what you would have in your Chat Completions API call
                    "model": settings.openai_llm_model,
                    "temperature": self.temperature,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": {
                                "pr_number": data["pr_number"],
                                "title": data["title"],
                                "body": data["body"],
                                "labels": ", ".join(data["labels"]),
                            },
                        },
                    ],
                },
            }
            tasks.append(task)

        try:
            logger.info(f"creating the file with {len(tasks)} tasks")
            # 1. Creating the file
            file_name = f"{self.data_dir}/batch_tasks_classify_prs.jsonl"
            with open(file_name, "w") as file:
                for obj in tasks:
                    file.write(json.dumps(obj) + "\n")

            # 2. create batch file
            logger.info("creating the batch file")
            batch_file = await self.client.files.create(
                purpose="batch",
                file=open(file_name, "rb"),
            )

            # 3. create batch job
            logger.info("creating the batch job")
            batch_job = await self.client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
            )

            # 4. get batch job results
            logger.info("waiting for the batch job to complete")
            batch_job = await self.client.batches.retrieve(batch_job.id)
            # time how long it tool to complete
            start_time = time.time()
            while batch_job.status != "completed":
                time.sleep(60)
                batch_job = await self.client.batches.retrieve(batch_job.id)
            end_time = time.time()
            logger.info(
                f"batch job completed in {round((end_time - start_time) / 60, 2)} minutes"
            )

            # 5. get batch job results
            logger.info("batch job completed")
            result_file_id = batch_job.output_file_id
            result = await self.client.files.content(result_file_id).content

            result_file_name = f"{self.data_dir}/batch_tasks_classify_prs.jsonl"

            with open(result_file_name, "wb") as file:
                file.write(result)

            # cleanup - delete the files
            _ = await self.client.files.delete(result_file_id)
            _ = await self.client.files.delete(batch_file.id)

            # Loading data from saved file
            logger.info("loading the results from the file")
            results = []
            with open(result_file_name, "r") as file:
                for line in file:
                    # Parsing the JSON string into a dict and appending to the list of results
                    json_object = json.loads(line.strip())
                    result = json_object["response"]["body"]["choices"][0]["message"][
                        "content"
                    ]
                    results.append(
                        {
                            "pr_number": json_object["pr_number"],
                            "pr_type": result,
                        }
                    )

            logger.info("batch processing done ...")
            return results
        except Exception as e:
            logger.error(
                {
                    "message": "Error processing batch",
                    "error": str(e),
                    "error_line": e.__traceback__.tb_lineno,
                }
            )
            raise e
