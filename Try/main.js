let currentUrl = '';  // Store the current URL
let currentQuestion = '';  // Store the current question

// Establish WebSocket connection
const ws = new WebSocket("ws://127.0.0.1:8004/ws");

// Handle successful WebSocket connection
ws.onopen = function() {
    console.log("WebSocket connection established!");
};

// Handle incoming messages from the WebSocket server
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log("Received data from server:", data);  // Log the data for debugging

    // Check if the server is asking for more information
    if (data.type === "info_request") {
        // Pre-fill the popup with stored URL and question values
        document.getElementById("popupUrlInput").value = currentUrl;
        document.getElementById("popupQuestionInput").value = currentQuestion;

        openPopup();  // Open the popup for additional information
    } else {
        // Handle the normal response from the server
        if (data.question && data.answer) {
            const tableBody = document.querySelector('#messagesTable tbody');

            const row = document.createElement('tr');

            // Create a table cell for the question
            const questionCell = document.createElement('td');
            questionCell.textContent = data.question;
            row.appendChild(questionCell);

            // Create a table cell for the answer
            const answerCell = document.createElement('td');
            answerCell.textContent = data.answer;
            row.appendChild(answerCell);

            // Create a table cell for the link
            const linkCell = document.createElement('td');
            if (data.link) {
                const linkAnchor = document.createElement('a');
                linkAnchor.href = data.link;
                linkAnchor.textContent = data.link;
                linkAnchor.target = "_blank";  // Open the link in a new tab
                linkCell.appendChild(linkAnchor);
            } else {
                linkCell.textContent = "No relevant link";
            }
            row.appendChild(linkCell);

            // Append the new row to the table body
            tableBody.appendChild(row);
        } else {
            console.error("Received incomplete data from the server: ", data);
        }
    }
};

// Open the popup to ask for more info
function openPopup() {
    document.getElementById("popup").style.display = "block";
}

// Close the popup
function closePopup() {
    document.getElementById("popup").style.display = "none";
}

// Send the additional information from the popup
function submitAdditionalInfo() {
    const additionalUrl = document.getElementById("popupUrlInput").value;
    const additionalQuestion = document.getElementById("popupQuestionInput").value;

    // Use the existing URL and question if the user doesn't provide new info
    const finalUrl = additionalUrl || currentUrl;  
    const finalQuestion = additionalQuestion || currentQuestion;

    // Update the current values with the new values if provided
    currentUrl = finalUrl;
    currentQuestion = finalQuestion;

    // Send the updated information back to the WebSocket server
    const message = JSON.stringify({
        type: "info_response",
        url: finalUrl,
        question: finalQuestion,
        user_choice: "detailed"
    });

    ws.send(message);

    // Close the popup after submitting
    closePopup();
}

// Send the initial request
function sendRequest() {
    const urlInput = document.getElementById("urlInput").value;
    const questionInput = document.getElementById("questionInput").value;

    // Update the current URL and question
    currentUrl = urlInput;
    currentQuestion = questionInput;

    const message = JSON.stringify({
        url: currentUrl,
        question: currentQuestion
    });

    ws.send(message);

    // Clear the input fields after sending
    document.getElementById("urlInput").value = '';
    document.getElementById("questionInput").value = '';
}
