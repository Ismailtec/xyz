/** @odoo-module */

import {patch} from "@web/core/utils/patch";
import {PosStore} from "@point_of_sale/app/store/pos_store";

/**
 * Base medical POS data management and bus updates
 * Works standalone for base medical practices
 */

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.setupMedicalBusListeners();
        console.log("Medical POS: Base medical data helpers loaded");
    },

    setupMedicalBusListeners() {
        try {
            // Use the existing bus service from POS
            if (this.env.services.bus_service) {
                const channel = `pos.session.${this.pos_session.id}`;

                this.env.services.bus_service.addEventListener(channel, ({detail}) => {
                    if (detail.type === 'critical_update') {
                        this.handleMedicalCriticalUpdate(detail);
                    } else if (detail.type === 'batch_sync') {
                        this.handleMedicalBatchSync(detail);
                    }
                });

                console.log("Medical POS: Base bus listeners set up successfully");
            }
        } catch (error) {
            console.error("Medical POS: Error setting up bus listeners:", error);
        }
    },

    handleMedicalCriticalUpdate(data) {
        const {model, operation, records} = data;

        try {
            if (this.models[model]) {
                if (operation === 'delete') {
                    records.forEach(record => {
                        this.models[model].delete(record.id);
                    });
                } else {
                    this.models[model].update(records);
                }

                console.log(`Medical POS: Updated ${model} via bus - ${operation}:`, records.length);
            }
        } catch (error) {
            console.error(`Medical POS: Error handling critical update for ${model}:`, error);
        }
    },

    handleMedicalBatchSync(data) {
        try {
            Object.keys(data.data).forEach(model => {
                if (this.models[model]) {
                    this.models[model].update(data.data[model]);
                }
            });

            console.log("Medical POS: Batch sync completed for models:", Object.keys(data.data));
        } catch (error) {
            console.error("Medical POS: Error handling batch sync:", error);
        }
    },

    // Base helper method to get pending items for partner
    getPendingItems(partnerId = null) {
        const allItems = this.models["ths.pending.pos.item"].getAll();

        if (partnerId) {
            return allItems.filter(item =>
                item.state === 'pending' &&
                item.partner_id && item.partner_id[0] === partnerId
            );
        }

        return allItems.filter(item => item.state === 'pending');
    }
});

console.log("Medical POS: Base data helpers loaded");