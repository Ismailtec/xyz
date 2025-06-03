/** @odoo-module */

import { patch } from "@web/core/utils/patch";
//import { OrderWidget } from "@point_of_sale/app/screens/order_widget/order_widget";
import { formatDateTime, formatDate } from "@web/core/l10n/dates";
import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";

/**
 * IMPORTANT: This follows Odoo 18 OWL 3 component patching methodology for veterinary extensions.
 * This is the LATEST approach for extending POS screen components with vet-specific functionality.
 * Patches the OrderWidget to add membership status display for pet owners.
 *
 * Veterinary-specific enhancement of OrderWidget
 * Adds membership status display for pet owners in the POS interface
 * Extends base medical functionality with veterinary membership features
 */
patch(OrderWidget.prototype, {
    /**
     * Helper function to format membership dates nicely for veterinary display
     * Handles date formatting using Odoo 18's latest date formatting utilities
     *
     * @param {string} dateString - Date string from backend (usually 'YYYY-MM-DD' format)
     * @returns {string} - Formatted date string for UI display
     */
    formatMembershipDate(dateString) {
        if (!dateString) {
            return "";
        }

        // Use Odoo 18's date formatting utilities for consistency
        try {
            // Assuming dateString is in 'YYYY-MM-DD' format from backend
            // Adjust format based on actual backend data if needed
            const date = new Date(dateString);

            // Check if date is valid to prevent display errors
            if (isNaN(date.getTime())) {
                console.warn("Vet POS: Invalid membership date format:", dateString);
                return dateString; // Return original string if invalid
            }

            // Use Odoo's formatDate utility for consistent formatting
            return formatDate(date);
        } catch (error) {
            console.error("Vet POS: Error formatting membership date:", error);
            return dateString; // Fallback to original string on error
        }
    },

    /**
     * Enhanced setup method for veterinary-specific initialization
     * Maintains parent functionality while adding vet-specific features
     */
    setup() {
        super.setup(); // REQUIRED: Call parent setup to maintain base functionality
        console.log("Vet POS: OrderWidget enhanced with veterinary membership features");
    },
});