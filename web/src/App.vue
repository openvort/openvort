<script setup lang="ts">
const vortTheme = {
    token: {
        colorPrimary: "#0f3eb9"
    }
};
</script>

<template>
    <VortConfigProvider :theme="vortTheme">
        <router-view />
    </VortConfigProvider>
</template>
