/** @odoo-module */

import { patch } from "@web/core/utils/patch";
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
     * FIXED: Helper function to format membership dates for veterinary display
     * Updated to use Odoo 18's latest date formatting utilities properly
     *
     * @param {string} dateString - Date string from backend (usually 'YYYY-MM-DD' format)
     * @returns {string} - Formatted date string for UI display
     */
    formatMembershipDate(dateString) {
        if (!dateString) {
            return "";
        }

        try {
            // FIXED: Enhanced date parsing to handle various backend formats
            let date;
            if (typeof dateString === 'string') {
                // Handle 'YYYY-MM-DD' format from backend
                date = new Date(dateString + 'T00:00:00'); // Add time to avoid timezone issues
            } else if (dateString instanceof Date) {
                date = dateString;
            } else {
                console.warn("Vet POS: Invalid membership date type:", typeof dateString, dateString);
                return dateString.toString();
            }

            // Check if date is valid to prevent display errors
            if (isNaN(date.getTime())) {
                console.warn("Vet POS: Invalid membership date format:", dateString);
                return dateString.toString(); // Return original string if invalid
            }

            // FIXED: Use Odoo 18's formatDate utility for consistent formatting
            return formatDate(date);
        } catch (error) {
            console.error("Vet POS: Error formatting membership date:", error);
            return dateString.toString(); // Fallback to string representation on error
        }
    },

    /**
     * FIXED: Enhanced setup method for veterinary-specific initialization
     * Updated to work with the latest OWL 3 component lifecycle
     * Maintains parent functionality while adding vet-specific features
     */
    setup() {
        super.setup(); // REQUIRED: Call parent setup to maintain base functionality
        console.log("Vet POS: OrderWidget enhanced with veterinary membership features for Odoo 18");

        // FIXED: Initialize any veterinary-specific reactive state if needed
        // This ensures proper reactivity with OWL 3's updated system
        try {
            // Any additional setup for vet-specific features can go here
            this.vetEnhancementsLoaded = true;
        } catch (error) {
            console.error("Vet POS: Error during veterinary setup:", error);
            this.vetEnhancementsLoaded = false;
        }
    },

    /**
     * FIXED: Get membership status color for visual indicators
     * Provides consistent color coding for different membership states
     *
     * @param {string} membershipState - The membership state from backend
     * @returns {string} - CSS class name for styling
     */
    getMembershipStatusColor(membershipState) {
        const colorMap = {
            'paid': 'text-success',
            'free': 'text-success',
            'invoiced': 'text-warning',
            'canceled': 'text-danger',
            'old': 'text-muted'
        };
        return colorMap[membershipState] || 'text-muted';
    },

    /**
     * FIXED: Get membership status display text
     * Provides user-friendly text for membership states
     *
     * @param {string} membershipState - The membership state from backend
     * @returns {string} - Display text for the membership state
     */
    getMembershipStatusText(membershipState) {
        const textMap = {
            'paid': 'Active Member',
            'free': 'Active Member',
            'invoiced': 'Member (Pending Payment)',
            'canceled': 'Membership Cancelled',
            'old': 'Membership Expired'
        };
        return textMap[membershipState] || `Membership: ${membershipState}`;
    }
});

console.log("Loaded FIXED vet product screen JS - compatible with Odoo 18 OWL 3:", "product_screen.js");