import { openai } from "@ai-sdk/openai";
import { streamText, StreamData } from "ai";
import { Pinecone } from "@pinecone-database/pinecone";

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

const pinecone = new Pinecone({
  apiKey: process.env.PINECONE_API_KEY!,
});

export async function POST(req: Request) {
  const { messages, notebooks } = await req.json();

  const latestMessage = messages[messages.length - 1];
  const query = latestMessage.content;

  try {
    // 1. Generate Embedding from OpenAI
    const embeddingResponse = await fetch(
      "https://api.openai.com/v1/embeddings",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "text-embedding-3-small",
          input: query,
          dimensions: 512,
        }),
      },
    );

    const embeddingData = await embeddingResponse.json();
    const queryVector = embeddingData.data[0].embedding;

    // 2. Query Pinecone
    const index = pinecone.Index(process.env.PINECONE_INDEX_NAME!);

    // Build metadata filter
    const metadataFilter: any = {
      user_email: process.env.USER_EMAIL,
    };

    // if (notebooks && notebooks.length > 0) {
    //   metadataFilter.notebook = { $in: notebooks };
    // }

    const searchResults = await index.query({
      vector: queryVector,
      topK: 5,
      filter: metadataFilter,
      includeMetadata: true,
    });

    // 3. Extract Context
    const contextText = searchResults.matches
      .filter((match) => match.metadata && match.metadata.text)
      .map(
        (match) =>
          `Source Notebook: ${match.metadata?.notebook}\nContent:\n${match.metadata?.text}`,
      )
      .join("\n\n---\n\n");

    // 4. Generate streaming response
    const systemPrompt = `You are PIE (Personal Intelligence Engine), an advanced AI study assistant. 
You answer questions exclusively based on the user's uploaded OneNote school notes provided below.

When you cite information, always mention the notebook it came from.
If the notes do not contain the answer, politely state that you cannot find the information in the current notebooks.

--- RETRIEVED CONTEXT ---
${contextText || "No relevant notes found for this query."}`;

    const sourcesList = searchResults.matches
      .map((m) => m.metadata?.source_file)
      .filter((s): s is string => typeof s === "string");

    // Initialize stream data for sources
    const data = new StreamData();
    data.append({
      type: "sources",
      sources: sourcesList,
    });

    const result = await streamText({
      model: openai("gpt-5-nano"),
      system: systemPrompt,
      messages,
      temperature: 1,
      onFinish() {
        data.close();
      },
    });

    return result.toDataStreamResponse({ data });
  } catch (error) {
    console.error("Error in chat route:", error);
    return new Response(
      JSON.stringify({ error: "Failed to process request" }),
      { status: 500 },
    );
  }
}
