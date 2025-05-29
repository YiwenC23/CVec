import os
import json
import streamlit as st
from prompts.mock_interview_prompt import get_default_instructions

def get_js_code():
    """Return the JavaScript code for WebRTC implementation"""
    return """
        document.addEventListener('DOMContentLoaded', function() {
            console.log("Script loaded");
            
            // Add debug logging for audio context
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(() => console.log("Microphone permission granted"))
                .catch(err => console.error("Microphone error:", err));
            
            const startButton = document.getElementById('startButton');
            const stopButton = document.getElementById('stopButton');
            const statusDiv = document.getElementById('status');
            const errorDiv = document.getElementById('error');
            
            let peerConnection = null;
            let audioStream = null;
            let dataChannel = null;
            
            const INITIAL_INSTRUCTIONS = INSTRUCTIONS_PLACEHOLDER;
            const API_KEY = API_KEY_PLACEHOLDER;
            
            // Add event listeners
            startButton.addEventListener('click', init);
            stopButton.addEventListener('click', stopRecording);
            
            let waitingForAssistant = true;   // start after first create
            
            async function init() {
                startButton.disabled = true;
                try {
                    updateStatus('Initializing...');
                    
                    // Connect directly to OpenAI's API
                    peerConnection = new RTCPeerConnection();
                    peerConnection.addTransceiver('audio', { direction: 'recvonly' });
                    await setupAudio();
                    setupDataChannel();
                    
                    const offer = await peerConnection.createOffer();
                    await peerConnection.setLocalDescription(offer);
                    
                    const sdpResponse = await fetch(`https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17`, {
                        method: "POST",
                        body: offer.sdp,
                        headers: {
                            Authorization: `Bearer ${API_KEY}`,
                            "Content-Type": "application/sdp",
                            "OpenAI-Beta": "realtime=v1"
                        },
                    });
                    
                    if (!sdpResponse.ok) {
                        throw new Error(`OpenAI API error: ${sdpResponse.status}`);
                    }
                    
                    const answer = {
                        type: "answer",
                        sdp: await sdpResponse.text(),
                    };
                    await peerConnection.setRemoteDescription(answer);
                    
                    updateStatus('Connected');
                    stopButton.disabled = false;
                    hideError();
                
                } catch (error) {
                    startButton.disabled = false;
                    stopButton.disabled = true;
                    showError('Error: ' + error.message);
                    console.error('Initialization error:', error);
                    updateStatus('Failed to connect');
                }
            }
            
            async function setupAudio() {
                try {
                    const audioEl = document.createElement("audio");
                    audioEl.autoplay = true;
                    document.body.appendChild(audioEl);
                    
                    audioStream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            sampleRate: 48000,
                            channelCount: 1
                        }
                    });
                    
                    peerConnection.ontrack = (event) => {
                        console.log("Received audio track");
                        audioEl.srcObject = event.streams[0];
                    };
                    
                    audioStream.getTracks().forEach(track => {
                        peerConnection.addTrack(track, audioStream);
                    });
                    
                    console.log("Audio setup completed");
                } catch (error) {
                    console.error("Error setting up audio:", error);
                    throw error;
                }
            }
            
            function setupDataChannel() {
                dataChannel = peerConnection.createDataChannel("oai-events");
                dataChannel.onopen = onDataChannelOpen;
                dataChannel.onmessage = handleMessage;
                dataChannel.onerror = (error) => {
                    console.error("DataChannel error:", error);
                    showError("DataChannel error: " + error.message);
                };
                console.log("DataChannel setup completed");
            }
            
            function handleMessage(event) {
                try {
                    const message = JSON.parse(event.data);
                    console.log('Received message:', message);
                    
                    switch (message.type) {
                        case "response.done":
                            handleTranscript(message);
                            break;
                        case "response.audio.delta":
                            handleAudioDelta(message);
                            break;
                        case "input_audio_buffer.speech_started":
                            console.log("Speech started");
                            createUserMessageContainer();
                            break;
                        case "input_audio_buffer.speech_ended":
                            console.log("Speech ended");
                            break;
                        case "conversation.item.input_audio_transcription.completed":
                            handleUserTranscript(message);
                            break;
                        case "error":
                            console.error("Error from API:", message.error);
                            showError(message.error.message);
                            break;
                        default:
                            console.log('Message type:', message.type);
                    }
                } catch (error) {
                    console.error('Error processing message:', error);
                    showError('Error processing message: ' + error.message);
                }
            }

            let currentUserMessage = null;

            function createUserMessageContainer() {
                const chatContainer = document.getElementById('chat-container');
                currentUserMessage = document.createElement('div');
                currentUserMessage.className = 'message user-message';

                const label = document.createElement('div');
                label.className = 'message-label';
                label.textContent = 'You';

                const content = document.createElement('div');
                content.className = 'message-content';

                currentUserMessage.appendChild(label);
                currentUserMessage.appendChild(content);
                chatContainer.appendChild(currentUserMessage);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            function handleUserTranscript(message) {
                if (currentUserMessage && message.transcript) {
                    const content = currentUserMessage.querySelector('.message-content');
                    if (content.textContent) {
                        content.textContent = content.textContent + " " + message.transcript;
                    } else {
                        content.textContent = message.transcript;
                    }
                    const chatContainer = document.getElementById('chat-container');
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    
                    if (!waitingForAssistant && /\\bdone[.!?]?$/i.test(message.transcript.trim())) {
                        sendResponseCreate();
                        waitingForAssistant = true;
                    }
                }
            }

            function handleAudioDelta(message) {
                if (message.delta) {
                    console.log("Received audio data");
                }
            }

            function handleTranscript(message) {
                const chatContainer = document.getElementById('chat-container');

                if (message.response?.output?.[0]?.content?.[0]?.transcript) {
                    const transcript = message.response.output[0].content[0].transcript;

                    const botMessage = document.createElement('div');
                    botMessage.className = 'message bot-message';

                    const label = document.createElement('div');
                    label.className = 'message-label';
                    label.textContent = 'Assistant';

                    const content = document.createElement('div');
                    content.className = 'message-content';
                    content.textContent = transcript;

                    botMessage.appendChild(label);
                    botMessage.appendChild(content);
                    chatContainer.appendChild(botMessage);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
                waitingForAssistant = false;
            }

            function sendSessionUpdate() {
                const sessionUpdateEvent = {
                    "type": "session.update",
                    "session": {
                        "instructions": INITIAL_INSTRUCTIONS,
                        "modalities": ["text", "audio"],
                        "voice": "echo",
                        "output_audio_format": "pcm16",
                        "input_audio_format": "pcm16",
                        "input_audio_transcription": {
                            "model": "whisper-1",
                            "language": "en",
                            "prompt": "Transcribe the audio and output the transcript only in English."
                            
                        }
                    }
                };
                sendMessage(sessionUpdateEvent);
            }

            function sendMessage(message) {
                if (dataChannel?.readyState === "open") {
                    dataChannel.send(JSON.stringify(message));
                    console.log('Sent message:', message);
                }
            }

            function onDataChannelOpen() {
                sendSessionUpdate();
                setTimeout(sendResponseCreate, 1000);
            }

            function sendResponseCreate() {
                sendMessage({ "type": "response.create" });
            }

            function stopRecording() {
                if (peerConnection) {
                    peerConnection.close();
                    peerConnection = null;
                }
                if (audioStream) {
                    audioStream.getTracks().forEach(track => track.stop());
                    audioStream = null;
                }
                if (dataChannel) {
                    dataChannel.close();
                    dataChannel = null;
                }

                /* ── NEW: reset UI & state ───────────────────────────── */
                const chatContainer = document.getElementById("chat-container");
                if (chatContainer) {
                    chatContainer.innerHTML = "";
                }
                waitingForAssistant = true;
                currentUserMessage = null;

                startButton.disabled = false;
                stopButton.disabled = true;
                updateStatus('Ready to start');
            }

            function updateStatus(message) {
                statusDiv.textContent = message;
            }

            function showError(message) {
                errorDiv.style.display = 'block';
                errorDiv.textContent = message;
            }

            function hideError() {
                errorDiv.style.display = 'none';
            }
        });
    """

def get_webrtc_html(resume_content, selected_job):
    """Generate the HTML for WebRTC interface"""
    interview_plan = get_default_instructions(resume_content, selected_job)
    api_key = openai_api_key
    js_code = get_js_code()
    js_code = js_code.replace('INSTRUCTIONS_PLACEHOLDER',json.dumps(interview_plan))
    js_code = js_code.replace('API_KEY_PLACEHOLDER', f'"{api_key}"')

    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Voice Chat</title>
        <style>
            /* Full-width container */
            .container {
                width: 100%;
                max-width: 100%;
                padding: 0 24px;            /* horizontal breathing room */
                box-sizing: border-box;
            }
            .controls {
                text-align: center;
                margin: 20px 0;
            }
            .chat-container {
                margin: 20px 0;
                padding: 16px;
                /* no border / no radius */
                min-height: 80vh;          /* slightly taller */
                max-height: 80vh;
                overflow-y: auto;
                background-color: inherit; /* same as page background */
            }
            .message {
                margin: 10px 0;
                padding: 10px 12px;
                border-radius: 8px;
                max-width: 80%;
            }
            .user-message {
                background-color: #e3f2fd;
                margin-left: auto;
                margin-right: 20px;
            }
            .bot-message {
                background-color: #f5f5f5;
                margin-left: 20px;
                margin-right: auto;
            }
            .message-label {
                font-size: 0.8em;
                color: #666;
                margin-bottom: 4px;
            }
            .status {
                text-align: center;
                margin: 10px 0;
                font-style: italic;
            }
            .error {
                color: red;
                display: none;
                margin: 10px 0;
            }
            button {
                padding: 10px 20px;
                margin: 0 10px;
                border-radius: 5px;
                border: none;
                background-color: #0066cc;
                color: white;
                cursor: pointer;
            }
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div id="status" class="status">Ready to start</div>
            <div id="error" class="error"></div>
            <div id="chat-container" class="chat-container"></div>
            <div class="controls">
                <button id="startButton">Start Interview</button>
                <button id="stopButton" disabled>End Interview</button>
            </div>
        </div>
        <script>
            JAVASCRIPT_CODE_PLACEHOLDER
        </script>
    </body>
    </html>
    '''.replace('JAVASCRIPT_CODE_PLACEHOLDER', js_code)

def main():
    slogan = "Hi, I'm Mock Interview Agent."
    image_url = "https://github.com/YiwenC23/DSCI560-group_labs/raw/main/lab9/scripts/icon.png?raw=true"
    st.markdown(
        f"""
        <div style='display: flex; flex-direction: column; align-items: center; text-align: center; margin: 0; padding: 0;'>
            <div style='font-style: italic; font-weight: 900; margin: 0; padding-top: 4px; display: flex; align-items: center; justify-content: center; flex-warp: warp; width: 100%;'>
                <img src={image_url} style='width: 45px; height: 45px;'>
                <span style='font-size: 26px; margin-left: 10px;'>
                    {slogan}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    #* Initialize session state of resume content and selected job
    resume_content = st.session_state["resume_content"] if "resume_content" in st.session_state else None
    selected_job = st.session_state["selected_job"] if "selected_job" in st.session_state else None
    
    if resume_content is None and selected_job is None:
        st.warning("Please upload your resume, and select a job first!")
    elif resume_content is None:
        st.warning("Please upload your resume first!")
    elif selected_job is None:
        st.warning("Please select a job first!")
    
    #* Create WebRTC container
    with st.container():
        st.components.v1.html(
            get_webrtc_html(resume_content, selected_job),
            height=800
        )

    st.markdown("""
        <style>
            .chat-container {
                margin: 20px 0;
                padding: 20px;
                background-color: inherit;
            }
            .webrtc-container {
                margin: 20px 0;
                text-align: center;
            }
            footer {
                visibility: hidden;
            }
        </style>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    #* Get OpenAI API Key
    with st.sidebar:
        if os.environ.get("OPENAI_API_KEY"):
            openai_api_key = st.text_input("OpenAI API Key", key="openai_api", type="password", value=os.environ.get("OPENAI_API_KEY"))
        else:
            openai_api_key = st.text_input("OpenAI API Key", key="openai_api", type="password")
    main()
