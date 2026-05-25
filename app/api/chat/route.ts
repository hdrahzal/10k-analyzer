import { streamText, convertToModelMessages } from "ai";

export async function POST(request: Request) {
  const { messages, documentContext } = await request.json();
  
  console.log("[v0] API received messages:", messages?.length, "context length:", documentContext?.length);

  const systemPrompt = `You are a financial analyst assistant specialized in analyzing SEC 10-K filings. You have been provided with the contents of a 10-K document.

DOCUMENT CONTEXT:
${documentContext}

INSTRUCTIONS:
1. Answer questions based ONLY on the information provided in the document above.
2. ALWAYS cite the specific page number(s) where you found the information using bold formatting like **Page 15** or **Pages 23-25**.
3. If you cannot find the answer in the document, clearly state that the information is not available in the provided 10-K.
4. Be precise and professional in your analysis.
5. When discussing financial figures, include the specific numbers from the document.
6. If a question is ambiguous, ask for clarification.

Remember: Every factual claim must include a page citation in bold.`;

  const result = streamText({
    model: "anthropic/claude-sonnet-4-20250514",
    system: systemPrompt,
    messages: await convertToModelMessages(messages),
  });

  return result.toUIMessageStreamResponse();
}
