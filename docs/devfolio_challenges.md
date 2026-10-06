### 1. Steganography Data Loss via Image Compression
**The Hurdle:** 
The core of our covert SOS feature relies on Least Significant Bit (LSB) steganography to hide encrypted text within the pixels of an image. During testing, we discovered that if a user shared the SOS image via standard messaging apps (like WhatsApp) or if they took a screenshot, the platform's native JPEG compression completely wiped the hidden LSB data. The message would be destroyed, and the decoder would crash silently.

**How We Overcame It:** 
We couldn't bypass third-party compression algorithms, so we re-engineered the user flow and error handling. 
*   **Engineering:** We implemented a robust magic header (`AEGIS01`) and a 4-byte payload length check before the actual hidden message bits. Now, if an image is corrupted by compression, the decoder instantly throws a clear "Corrupted/Compressed Image" error rather than failing silently. 
*   **UX Pivot:** We restricted the output strictly to lossless PNG formats and utilized the browser's native Web Share API to send the image as a raw file attachment, bypassing platform compression. We also added explicit UI warnings against taking screenshots.

### 2. The Next.js URL History Trace (The Disguise Problem)
**The Hurdle:** 
The app is disguised as a calculator. Initially, we used standard Next.js routing (`/calculator` to `/dashboard`). However, we realized that navigating between pages leaves a trail in the browser history. If a monitor checked the phone's history, they would clearly see the user was not just doing math. 

**How We Overcame It:** 
We abandoned standard URL routing for the core stealth transition. We architected the frontend so the calculator and the actual safety dashboard share the exact same root route (`/`). Entering the secret PIN (`2580 =`) triggers a client-side React state change that dynamically mounts the dashboard *over* the calculator without ever updating the URL or pushing to the history API. When the "Quick Exit" (Escape) is triggered, it simply unmounts the component and purges all local state, leaving zero digital footprints.

### 3. Hallucination Control within a "Zero-Cost" RAG Pipeline
**The Hurdle:** 
To provide legal advice, we needed an AI that strictly cited the Protection of Women from Domestic Violence Act (PWDVA) and the Bharatiya Nyaya Sanhita (BNS) without hallucinating. To keep the project zero-cost, we had to use MongoDB Atlas's free M0 tier for our Vector Store, which has a strict 512MB limit—far too small for a massive legal embedding database.

**How We Overcame It:** 
Instead of relying on large cloud embedding APIs, we ran `sentence-transformers/all-MiniLM-L6-v2` locally within our FastAPI backend. We ruthlessly curated and chunked only the most relevant, high-impact sections of the Indian legal codes rather than indexing the entire constitution. By keeping the corpus hyper-focused, we created a highly dense, incredibly accurate Vector Search index that easily fit within the free tier limits. We then strictly prompted the Groq LLM to *only* answer using the retrieved MongoDB context chunks, entirely eliminating hallucinations.

### 4. Overcoming Free-Tier API Rate Limits & Cold Starts
**The Hurdle:** 
Operating on a completely free stack meant dealing with Groq API rate limits (Too Many Requests) and 30-50 second cold-starts on our Render-hosted FastAPI backend. During rapid testing or multi-turn emotional support chats, the AI would frequently time out.

**How We Overcame It:** 
We built a resilient, offline-capable fallback architecture. The backend catches API rate limit exceptions or network timeouts and instantly routes the request to a pre-configured local fallback mechanism so the user is never left hanging. For the Render cold starts, we built an explicit loading state sequence in the UI to manage user expectations during the initial boot, ensuring the app feels responsive even when the server is waking up.
