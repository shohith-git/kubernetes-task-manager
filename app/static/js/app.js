
document.addEventListener("DOMContentLoaded", function () {

    // SIDEBAR TOGGLE

    const menuButtons = document.querySelectorAll(".menu-toggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");

    const isMobile = () => window.innerWidth <= 768;

    function updateMenuState() {
        menuButtons.forEach(function (button) {
            const expanded = isMobile()
                ? document.body.classList.contains("sidebar-open")
                : !document.body.classList.contains("sidebar-collapsed");

            button.setAttribute("aria-expanded", String(expanded));
        });
    }

    menuButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            if (isMobile()) {
                document.body.classList.toggle("sidebar-open");
            } else {
                document.body.classList.toggle("sidebar-collapsed");
            }

            updateMenuState();
        });

    });

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener("click", function () {
            document.body.classList.remove("sidebar-open");
            updateMenuState();
        });
    }

    document.querySelectorAll(".sidebar-nav a").forEach(function (link) {
        link.addEventListener("click", function () {
            if (isMobile()) {
                document.body.classList.remove("sidebar-open");
                updateMenuState();
            }
        });
    });

    window.addEventListener("resize", function () {
        document.body.classList.remove("sidebar-open");
        updateMenuState();
    });

    updateMenuState();


    // FLASH MESSAGE AUTO DISMISS

    const flashMessages = document.querySelectorAll(".flash-message");

    flashMessages.forEach(function (message) {
        setTimeout(function () {
            message.style.transition = "opacity 0.5s ease";
            message.style.opacity = "0";

            setTimeout(function () {
                message.remove();
            }, 500);
        }, 4000);
    });


    // DELETE CONFIRMATION

    const deleteForms = document.querySelectorAll('form[action*="/delete"]');

    deleteForms.forEach(function (form) {
        form.addEventListener("submit", function (event) {
            const confirmed = confirm(
                "Are you sure you want to delete this task? This action cannot be undone."
            );

            if (!confirmed) {
                event.preventDefault();
            }
        });
    });


    // DUE DATE VALIDATION

    const dueDateInput = document.getElementById("due_date");

    if (dueDateInput && !dueDateInput.value) {
        const today = new Date();

        const localDate = new Date(
            today.getTime() - today.getTimezoneOffset() * 60000
        ).toISOString().split("T")[0];

        dueDateInput.min = localDate;
    }

});
