/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OrderWidget } from "@point_of_sale/app/screens/order_widget/order_widget";
import { formatDateTime, formatDate } from "@web/core/l10n/dates"; // Import date formatting utilities

patch(OrderWidget.prototype, {
    // Helper function to format the membership date nicely
    formatMembershipDate(dateString) {
        if (!dateString) {
            return "";
        }
        // Use Odoo's date formatting for consistency
        // formatDate is usually sufficient for just the date part
        try {
             // Assuming dateString is in 'YYYY-MM-DD' format from backend
             // Adjust format based on actual backend data if needed
             const date = new Date(dateString); // Basic parsing
             if (isNaN(date.getTime())) { // Check if date is valid
                 return dateString; // Return original string if invalid
             }
            return formatDate(date); // Use Odoo's formatter
        } catch (e) {
            console.error("Error formatting membership date:", e);
            return dateString; // Fallback to original string
        }
    }
});