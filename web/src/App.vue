<script setup lang="ts">
const vortTheme = {
    token: {
        colorPrimary: "#0f3eb9",
        borderRadius: 4
    }
};
</script>

<template>
    <VortConfigProvider :get-popup-container="true" :theme="vortTheme">
        <router-view />
    </VortConfigProvider>
</template>
